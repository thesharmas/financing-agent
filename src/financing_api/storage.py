"""GCS-backed PDF storage with SHA-256 content deduplication.

Lifted (with simplifications) from the deleted financing_proxy.firestore
module. Same bucket, same dedup scheme: blob name is the hex sha256 of
the raw PDF bytes, so identical PDFs occupy one object.

Sync-only: FastAPI callers should offload via asyncio.to_thread.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from google.cloud import storage

_client: storage.Client | None = None


def _get_client(project: str) -> storage.Client:
    global _client
    if _client is None:
        _client = storage.Client(project=project)
    return _client


@dataclass(frozen=True)
class StoredPdf:
    gcs_uri: str
    content_hash: str
    is_new: bool


def store_pdf(*, project: str, bucket_name: str, pdf_base64: str) -> StoredPdf:
    """Upload PDF to gs://<bucket>/<sha256>.pdf, skipping if already present."""
    pdf_bytes = base64.b64decode(pdf_base64)
    content_hash = hashlib.sha256(pdf_bytes).hexdigest()
    blob_name = f"{content_hash}.pdf"
    gcs_uri = f"gs://{bucket_name}/{blob_name}"

    bucket = _get_client(project).bucket(bucket_name)
    blob = bucket.blob(blob_name)

    if blob.exists():
        return StoredPdf(gcs_uri=gcs_uri, content_hash=content_hash, is_new=False)

    blob.upload_from_string(pdf_bytes, content_type="application/pdf")
    return StoredPdf(gcs_uri=gcs_uri, content_hash=content_hash, is_new=True)


def fetch_pdf(*, project: str, gcs_uri: str) -> str:
    """Fetch a previously stored PDF, return as base64."""
    path = gcs_uri.removeprefix("gs://")
    bucket_name, blob_name = path.split("/", 1)
    blob = _get_client(project).bucket(bucket_name).blob(blob_name)
    return base64.standard_b64encode(blob.download_as_bytes()).decode()
