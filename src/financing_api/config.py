"""Runtime configuration for financing_api.

Reads from environment. Values without sensible defaults are required and
will be validated by callers (e.g. at startup) rather than silently
defaulting to something wrong.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


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

    # Managed agent
    agent_id: str
    environment_id: str
    vault_id: str

    # CORS
    allowed_origins: list[str]


def _req(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"missing required env var: {name}")
    return v


def _load_agent_ids() -> tuple[str, str, str]:
    """Prefer env vars; fall back to AGENT_CONFIG_PATH JSON file if set."""
    env_ids = (
        os.environ.get("AGENT_ID"),
        os.environ.get("ENVIRONMENT_ID"),
        os.environ.get("VAULT_ID"),
    )
    if all(env_ids):
        return env_ids  # type: ignore[return-value]

    path = os.environ.get("AGENT_CONFIG_PATH")
    if path:
        data = json.loads(Path(path).read_text())
        return data["agent_id"], data["environment_id"], data["vault_id"]

    raise RuntimeError(
        "missing agent IDs: set AGENT_ID/ENVIRONMENT_ID/VAULT_ID or AGENT_CONFIG_PATH"
    )


def load_settings() -> Settings:
    agent_id, environment_id, vault_id = _load_agent_ids()
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
        agent_id=agent_id,
        environment_id=environment_id,
        vault_id=vault_id,
        allowed_origins=os.environ.get(
            "ALLOWED_ORIGINS", "http://localhost:3000"
        ).split(","),
    )
