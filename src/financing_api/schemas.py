"""Pydantic request/response models for the API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    tx_hash: str = Field(..., min_length=66, max_length=66)
    pdf_base64: str = Field(..., min_length=1)
    title: str = "offer.pdf"


class VerifyRequest(BaseModel):
    tx_hash: str = Field(..., min_length=66, max_length=66)


class VerifyResponse(BaseModel):
    ok: bool
    from_address: str | None = None
    to_address: str | None = None
    amount_usdc: str | None = None
    block_number: int | None = None
    error: str | None = None
