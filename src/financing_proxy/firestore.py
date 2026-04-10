"""Firestore client for client registration and usage tracking."""

from datetime import datetime, timezone

from google.cloud import firestore

from financing_proxy.auth import get_key_prefix, hash_api_key
from financing_proxy.config import FIRESTORE_COLLECTION, GCP_PROJECT

_db = None


def _get_db() -> firestore.Client:
    """Lazy-initialize Firestore client."""
    global _db
    if _db is None:
        _db = firestore.Client(project=GCP_PROJECT)
    return _db


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


def get_usage(doc_id: str) -> dict | None:
    """Get usage stats for a client."""
    db = _get_db()
    doc = db.collection(FIRESTORE_COLLECTION).document(doc_id).get()
    if doc.exists:
        data = doc.to_dict()
        return {
            "name": data["name"],
            "company": data["company"],
            "created_at": data["created_at"],
            "usage": data["usage"],
        }
    return None
