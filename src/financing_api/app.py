"""FastAPI app: health check + payment verification (step-by-step build).

At this stage: /health and /verify only. /analyze lands once the
Firestore ledger, GCS storage, and agent invocation are in place.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from financing_api.config import load_settings
from financing_api.payments import PaymentError, verify_payment
from financing_api.schemas import VerifyRequest, VerifyResponse

settings = load_settings()

app = FastAPI(title="financing-api", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/verify", response_model=VerifyResponse)
async def verify(req: VerifyRequest) -> VerifyResponse:
    """Verify a Tempo testnet payment. Stateless — no idempotency yet."""
    try:
        payment = await verify_payment(
            rpc_url=settings.tempo_rpc_url,
            tx_hash=req.tx_hash,
            usdc_address=settings.usdc_address,
            usdc_decimals=settings.usdc_decimals,
            expected_to=settings.treasury_address,
            expected_amount_usdc=Decimal(settings.price_usdc),
        )
    except PaymentError as e:
        return VerifyResponse(ok=False, error=str(e))
    except Exception as e:  # noqa: BLE001 — surface anything unexpected
        raise HTTPException(status_code=502, detail=f"verify failed: {e}")

    return VerifyResponse(
        ok=True,
        from_address=payment.from_address,
        to_address=payment.to_address,
        amount_usdc=str(payment.amount_usdc),
        block_number=payment.block_number,
    )
