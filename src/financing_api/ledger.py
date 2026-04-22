"""Firestore ledger: payment idempotency + analysis run records.

Two collections:
    payments/<tx_hash_lower>    single-use record of a confirmed on-chain payment
    analysis_runs/<auto_id>     per-run execution log (PDF, agent output, tokens)

The `payments` collection is the idempotency primitive: a tx_hash can be
consumed exactly once. Concurrent requests for the same hash race on a
Firestore transaction; losers see PaymentAlreadyConsumed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore

_db: firestore.Client | None = None


class PaymentAlreadyConsumed(Exception):
    """Raised when a tx_hash has already been used for a paid run."""


def _get_db(project: str) -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client(project=project)
    return _db


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class PaymentRecord:
    tx_hash: str
    from_address: str
    to_address: str
    amount_usdc: str
    run_id: str


def consume_payment(
    *,
    project: str,
    collection: str,
    tx_hash: str,
    from_address: str,
    to_address: str,
    amount_usdc: str,
    run_id: str,
) -> None:
    """Atomically mark a tx_hash as consumed. Raises if already used.

    Uses a Firestore transaction so two concurrent callers can't both
    claim the same payment.
    """
    db = _get_db(project)
    ref = db.collection(collection).document(tx_hash.lower())

    transaction = db.transaction()

    @firestore.transactional
    def _claim(txn: firestore.Transaction) -> None:
        snap = ref.get(transaction=txn)
        if snap.exists:
            raise PaymentAlreadyConsumed(tx_hash)
        txn.set(
            ref,
            {
                "tx_hash": tx_hash,
                "from_address": from_address,
                "to_address": to_address,
                "amount_usdc": amount_usdc,
                "run_id": run_id,
                "consumed_at": _now(),
            },
        )

    _claim(transaction)


def create_run(
    *,
    project: str,
    collection: str,
    tx_hash: str,
    payer_address: str,
    gcs_uri: str,
    content_hash: str,
    pdf_is_new: bool,
) -> str:
    """Create a new analysis_runs doc in 'running' state. Returns its ID."""
    db = _get_db(project)
    ref = db.collection(collection).document()
    ref.set(
        {
            "tx_hash": tx_hash,
            "payer_address": payer_address,
            "gcs_uri": gcs_uri,
            "content_hash": content_hash,
            "pdf_is_new": pdf_is_new,
            "started_at": _now(),
            "completed_at": None,
            "status": "running",
            "full_text": "",
            "tool_calls": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "error": None,
        }
    )
    return ref.id


def update_run(
    *,
    project: str,
    collection: str,
    run_id: str,
    **fields: Any,
) -> None:
    """Patch an existing run doc. Adds completed_at when status is terminal."""
    db = _get_db(project)
    if fields.get("status") in {"completed", "failed"} and "completed_at" not in fields:
        fields["completed_at"] = _now()
    db.collection(collection).document(run_id).update(fields)
