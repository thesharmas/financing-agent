"""Firestore client for client registration and usage tracking."""

import base64
import hashlib
import os
from datetime import datetime, timezone

from google.cloud import firestore, storage

from financing_proxy.auth import get_key_prefix, hash_api_key
from financing_proxy.config import FIRESTORE_COLLECTION, GCP_PROJECT

PDF_BUCKET = os.environ.get("PDF_BUCKET", "financing-agent-pdfs")

_db = None
_gcs = None


def _get_db() -> firestore.Client:
    """Lazy-initialize Firestore client."""
    global _db
    if _db is None:
        _db = firestore.Client(project=GCP_PROJECT)
    return _db


def _get_gcs() -> storage.Client:
    """Lazy-initialize GCS client."""
    global _gcs
    if _gcs is None:
        _gcs = storage.Client(project=GCP_PROJECT)
    return _gcs


def store_pdf(pdf_base64: str) -> tuple[str, str, bool]:
    """Store PDF in GCS, deduped by content hash.

    Returns (gcs_uri, content_hash, is_new).
    If the PDF already exists, skips upload and returns the existing URI.
    """
    pdf_bytes = base64.b64decode(pdf_base64)
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()
    blob_name = f"{content_hash}.pdf"
    gcs_uri = f"gs://{PDF_BUCKET}/{blob_name}"

    bucket = _get_gcs().bucket(PDF_BUCKET)
    blob = bucket.blob(blob_name)

    if blob.exists():
        return gcs_uri, content_hash, False

    blob.upload_from_string(pdf_bytes, content_type="application/pdf")
    return gcs_uri, content_hash, True


def fetch_pdf_from_gcs(gcs_uri: str) -> str:
    """Fetch PDF from GCS and return as base64 string."""
    # Parse gs://bucket/blob
    path = gcs_uri.replace("gs://", "")
    bucket_name, blob_name = path.split("/", 1)

    bucket = _get_gcs().bucket(bucket_name)
    blob = bucket.blob(blob_name)
    pdf_bytes = blob.download_as_bytes()
    return base64.standard_b64encode(pdf_bytes).decode()


def register_client(
    name: str, email: str, company: str, api_key: str
) -> dict:
    """Store a new client record. Returns the document data (without the hash)."""
    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()

    doc_data = {
        "api_key_hash": hash_api_key(api_key),
        "api_key_prefix": get_key_prefix(api_key),
        "name": name,
        "email": email,
        "company": company,
        "created_at": now,
        "active": True,
        "usage": {
            "total_calls": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "last_called_at": None,
        },
    }

    db.collection(FIRESTORE_COLLECTION).add(doc_data)
    return {
        "name": name,
        "email": email,
        "company": company,
        "created_at": now,
    }


def validate_api_key(api_key: str) -> dict | None:
    """Validate an API key. Returns the client record if valid, None if not.

    Uses prefix index for fast lookup, then verifies the full hash.
    """
    db = _get_db()
    prefix = get_key_prefix(api_key)
    key_hash = hash_api_key(api_key)

    # Query by prefix (fast — indexed field)
    docs = (
        db.collection(FIRESTORE_COLLECTION)
        .where("api_key_prefix", "==", prefix)
        .where("active", "==", True)
        .stream()
    )

    for doc in docs:
        data = doc.to_dict()
        if data["api_key_hash"] == key_hash:
            return {"doc_id": doc.id, **data}

    return None


def increment_usage(doc_id: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
    """Increment usage counters for a client."""
    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()

    db.collection(FIRESTORE_COLLECTION).document(doc_id).update({
        "usage.total_calls": firestore.Increment(1),
        "usage.total_input_tokens": firestore.Increment(input_tokens),
        "usage.total_output_tokens": firestore.Increment(output_tokens),
        "usage.last_called_at": now,
    })


def log_run(
    client_doc_id: str,
    pdf_title: str,
    pdf_base64: str,
    message: str,
    output: str,
    tool_calls: list[dict],
    mcp_tool_inputs: list[dict] | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> str:
    """Log an analysis run for eval tracking. Returns the run document ID."""
    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()

    # Store PDF in GCS (deduped by content hash)
    gcs_uri, content_hash, is_new = store_pdf(pdf_base64)

    doc_data = {
        "client_doc_id": client_doc_id,
        "pdf_title": pdf_title,
        "pdf_gcs_uri": gcs_uri,
        "pdf_content_hash": content_hash,
        "pdf_is_new": is_new,
        "message": message,
        "output": output,
        "tool_calls": tool_calls,
        "mcp_tool_inputs": mcp_tool_inputs or [],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "created_at": now,
        "eval_status": "pending",
        "eval_scores": {},
    }

    _, doc_ref = db.collection("financing_runs").add(doc_data)
    return doc_ref.id


def get_pending_runs(limit: int = 50) -> list[dict]:
    """Get runs that haven't been evaluated yet."""
    db = _get_db()
    docs = (
        db.collection("financing_runs")
        .where("eval_status", "==", "pending")
        .limit(limit)
        .stream()
    )
    return [{"doc_id": doc.id, **doc.to_dict()} for doc in docs]


def save_eval_scores(run_doc_id: str, scores: dict) -> None:
    """Save eval scores for a run and mark it as evaluated."""
    db = _get_db()
    db.collection("financing_runs").document(run_doc_id).update({
        "eval_scores": scores,
        "eval_status": "evaluated",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    })


def get_eval_runs(status: str | None = None, limit: int = 20) -> list[dict]:
    """Get eval runs, optionally filtered by status. Returns summary (no PDF data)."""
    db = _get_db()
    query = db.collection("financing_runs")
    if status:
        query = query.where("eval_status", "==", status)
    query = query.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)

    runs = []
    for doc in query.stream():
        data = doc.to_dict()
        scores = data.get("eval_scores", {})
        runs.append({
            "run_id": doc.id,
            "pdf_title": data.get("pdf_title"),
            "created_at": data.get("created_at"),
            "eval_status": data.get("eval_status"),
            "evaluated_at": data.get("evaluated_at"),
            "passed": scores.get("passed"),
            "agreement_rate": scores.get("agreement_rate"),
            "disagreements": scores.get("disagreements", []),
            "error": scores.get("error"),
        })
    return runs


def get_eval_run_detail(run_id: str) -> dict | None:
    """Get full eval detail for a single run (no PDF data)."""
    db = _get_db()
    doc = db.collection("financing_runs").document(run_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    return {
        "run_id": doc.id,
        "pdf_title": data.get("pdf_title"),
        "created_at": data.get("created_at"),
        "eval_status": data.get("eval_status"),
        "evaluated_at": data.get("evaluated_at"),
        "eval_scores": data.get("eval_scores", {}),
        "mcp_tool_inputs": data.get("mcp_tool_inputs", []),
        "tool_calls": data.get("tool_calls", []),
        "output_preview": data.get("output", "")[:500],
    }


def get_usage(doc_id: str) -> dict | None:
    """Get client-facing usage stats (no token counts — those are internal)."""
    db = _get_db()
    doc = db.collection(FIRESTORE_COLLECTION).document(doc_id).get()
    if doc.exists:
        data = doc.to_dict()
        usage = data.get("usage", {})
        return {
            "name": data["name"],
            "company": data["company"],
            "created_at": data["created_at"],
            "total_calls": usage.get("total_calls", 0),
            "last_called_at": usage.get("last_called_at"),
        }
    return None
