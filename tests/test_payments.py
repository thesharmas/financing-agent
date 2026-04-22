"""Unit tests for financing_api.payments."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from financing_api.payments import (
    TRANSFER_TOPIC,
    PaymentError,
    parse_transfer,
    verify_payment,
)

USDC = "0x20c0000000000000000000000000000000000000"
TREASURY = "0x275dBcf26B21e1687d8322Ba4f43C77FDa9A7A45"
PAYER = "0x1111111111111111111111111111111111111111"


def _addr_topic(addr: str) -> str:
    return "0x" + "0" * 24 + addr[2:].lower()


def _amount_data(raw: int) -> str:
    return "0x" + raw.to_bytes(32, "big").hex()


def _receipt(status: str = "0x1", amount_raw: int = 2_000_000, to: str = TREASURY) -> dict:
    return {
        "status": status,
        "blockNumber": "0x64",
        "logs": [
            {
                "address": USDC,
                "topics": [TRANSFER_TOPIC, _addr_topic(PAYER), _addr_topic(to)],
                "data": _amount_data(amount_raw),
            }
        ],
    }


class TestParseTransfer:
    def test_extracts_from_to_amount(self):
        from_a, to_a, amt = parse_transfer(_receipt(), USDC)
        assert from_a.lower() == PAYER.lower()
        assert to_a.lower() == TREASURY.lower()
        assert amt == 2_000_000

    def test_ignores_logs_from_other_contracts(self):
        r = _receipt()
        r["logs"].insert(0, {"address": "0xdead", "topics": [], "data": "0x"})
        _, to_a, _ = parse_transfer(r, USDC)
        assert to_a.lower() == TREASURY.lower()

    def test_raises_when_no_matching_log(self):
        r = _receipt()
        r["logs"] = []
        with pytest.raises(PaymentError, match="no USDC Transfer"):
            parse_transfer(r, USDC)


class TestVerifyPayment:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        with patch(
            "financing_api.payments.fetch_receipt",
            new=AsyncMock(return_value=_receipt()),
        ):
            result = await verify_payment(
                rpc_url="x",
                tx_hash="0x" + "a" * 64,
                usdc_address=USDC,
                usdc_decimals=6,
                expected_to=TREASURY,
                expected_amount_usdc=Decimal("2"),
            )
        assert result.amount_usdc == Decimal("2")
        assert result.to_address.lower() == TREASURY.lower()
        assert result.from_address.lower() == PAYER.lower()

    @pytest.mark.asyncio
    async def test_rejects_failed_tx(self):
        with patch(
            "financing_api.payments.fetch_receipt",
            new=AsyncMock(return_value=_receipt(status="0x0")),
        ):
            with pytest.raises(PaymentError, match="failed on-chain"):
                await verify_payment(
                    rpc_url="x",
                    tx_hash="0x" + "a" * 64,
                    usdc_address=USDC,
                    usdc_decimals=6,
                    expected_to=TREASURY,
                    expected_amount_usdc=Decimal("2"),
                )

    @pytest.mark.asyncio
    async def test_rejects_wrong_recipient(self):
        with patch(
            "financing_api.payments.fetch_receipt",
            new=AsyncMock(return_value=_receipt(to="0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef")),
        ):
            with pytest.raises(PaymentError, match="recipient mismatch"):
                await verify_payment(
                    rpc_url="x",
                    tx_hash="0x" + "a" * 64,
                    usdc_address=USDC,
                    usdc_decimals=6,
                    expected_to=TREASURY,
                    expected_amount_usdc=Decimal("2"),
                )

    @pytest.mark.asyncio
    async def test_rejects_underpayment(self):
        with patch(
            "financing_api.payments.fetch_receipt",
            new=AsyncMock(return_value=_receipt(amount_raw=1_000_000)),  # $1
        ):
            with pytest.raises(PaymentError, match="underpaid"):
                await verify_payment(
                    rpc_url="x",
                    tx_hash="0x" + "a" * 64,
                    usdc_address=USDC,
                    usdc_decimals=6,
                    expected_to=TREASURY,
                    expected_amount_usdc=Decimal("2"),
                )
