"""Runtime configuration for financing_api.

Reads from environment. Values without sensible defaults are required and
will be validated by callers (e.g. at startup) rather than silently
defaulting to something wrong.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Tempo testnet chain
    tempo_rpc_url: str
    treasury_address: str
    usdc_address: str
    usdc_decimals: int

    # Pricing (in whole USDC units — e.g. "2" means $2.00)
    price_usdc: str

    # Google Cloud
    gcp_project: str
    pdf_bucket: str
    payments_collection: str
    runs_collection: str

    # CORS
    allowed_origins: list[str]


def _req(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"missing required env var: {name}")
    return v


def load_settings() -> Settings:
    return Settings(
        tempo_rpc_url=os.environ.get(
            "TEMPO_RPC_URL", "https://rpc.moderato.tempo.xyz"
        ),
        treasury_address=_req("TREASURY_ADDRESS"),
        usdc_address=_req("USDC_ADDRESS"),
        usdc_decimals=int(os.environ.get("USDC_DECIMALS", "6")),
        price_usdc=os.environ.get("PRICE_USDC", "2"),
        gcp_project=os.environ.get("GCP_PROJECT", "kanmonos-prod"),
        pdf_bucket=os.environ.get("PDF_BUCKET", "financing-agent-pdfs"),
        payments_collection=os.environ.get(
            "FIRESTORE_PAYMENTS_COLLECTION", "payments"
        ),
        runs_collection=os.environ.get("FIRESTORE_RUNS_COLLECTION", "analysis_runs"),
        allowed_origins=os.environ.get(
            "ALLOWED_ORIGINS", "http://localhost:3000"
        ).split(","),
    )
