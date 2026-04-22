"""Tempo RPC payment verification.

Given a tx_hash, fetch the receipt, decode the ERC-20 Transfer event
log emitted by the configured USDC contract, and confirm the transfer
went to the treasury address for at least the expected amount.

This is the Python port of frontend/app/api/verify/route.ts — same
logic, same check, no idempotency (that lives in ledger.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

# keccak256("Transfer(address,address,uint256)")
TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)


class PaymentError(Exception):
    """Raised when a payment cannot be verified or is invalid."""


@dataclass(frozen=True)
class VerifiedPayment:
    tx_hash: str
    from_address: str
    to_address: str
    amount_usdc: Decimal
    block_number: int


async def fetch_receipt(rpc_url: str, tx_hash: str) -> dict[str, Any]:
    """Call eth_getTransactionReceipt. Returns the raw receipt dict.

    Raises PaymentError if the tx isn't found or the RPC errors.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_getTransactionReceipt",
                "params": [tx_hash],
            },
        )
        r.raise_for_status()
        body = r.json()

    if "error" in body:
        raise PaymentError(f"rpc error: {body['error']}")
    result = body.get("result")
    if not result:
        raise PaymentError("transaction not found or not yet mined")
    return result


def _hex_topic_to_address(topic: str) -> str:
    """Transfer event topics are 32-byte left-padded addresses. Return 0x+40-hex."""
    # topic is "0x" + 64 hex chars; address is last 40 chars
    return "0x" + topic[-40:]


def parse_transfer(
    receipt: dict[str, Any],
    usdc_address: str,
) -> tuple[str, str, int]:
    """Find the Transfer log emitted by the USDC contract in this receipt.

    Returns (from, to, raw_amount). Raises PaymentError if no matching log.
    """
    usdc_lower = usdc_address.lower()
    for log in receipt.get("logs", []):
        if log.get("address", "").lower() != usdc_lower:
            continue
        topics = log.get("topics", [])
        if len(topics) < 3 or topics[0].lower() != TRANSFER_TOPIC:
            continue
        from_addr = _hex_topic_to_address(topics[1])
        to_addr = _hex_topic_to_address(topics[2])
        raw_amount = int(log.get("data", "0x0"), 16)
        return from_addr, to_addr, raw_amount
    raise PaymentError("no USDC Transfer log in receipt")


async def verify_payment(
    *,
    rpc_url: str,
    tx_hash: str,
    usdc_address: str,
    usdc_decimals: int,
    expected_to: str,
    expected_amount_usdc: Decimal,
) -> VerifiedPayment:
    """Full verification: receipt + decoded Transfer + recipient + amount."""
    receipt = await fetch_receipt(rpc_url, tx_hash)

    # receipt.status is "0x1" on success in JSON-RPC
    if receipt.get("status") != "0x1":
        raise PaymentError(f"transaction failed on-chain (status={receipt.get('status')})")

    from_addr, to_addr, raw_amount = parse_transfer(receipt, usdc_address)

    if to_addr.lower() != expected_to.lower():
        raise PaymentError(
            f"recipient mismatch: expected {expected_to}, got {to_addr}"
        )

    amount = Decimal(raw_amount) / (Decimal(10) ** usdc_decimals)
    if amount < expected_amount_usdc:
        raise PaymentError(
            f"underpaid: expected {expected_amount_usdc} USDC, got {amount}"
        )

    return VerifiedPayment(
        tx_hash=tx_hash,
        from_address=from_addr,
        to_address=to_addr,
        amount_usdc=amount,
        block_number=int(receipt.get("blockNumber", "0x0"), 16),
    )
