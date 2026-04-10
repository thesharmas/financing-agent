"""Proxy configuration.

All values come from environment variables. No defaults for sensitive IDs.
Set these on Cloud Run or in your local environment before running.

Required env vars:
    AGENT_ID           — Managed Agent ID from financing_agent.setup
    ENVIRONMENT_ID     — Environment ID from financing_agent.setup
    VAULT_ID           — Vault ID from financing_agent.setup

Optional env vars:
    GCP_PROJECT            — GCP project for Firestore (default: kanmonos-prod)
    FIRESTORE_COLLECTION   — Firestore collection name (default: financing_clients)
"""

import os
import sys


def _require_env(name: str) -> str:
    """Get a required environment variable or exit with an error."""
    value = os.environ.get(name)
    if not value:
        print(f"ERROR: {name} environment variable is required")
        sys.exit(1)
    return value


# Lazy-loaded — only resolved when the proxy actually starts
_agent_id = None
_environment_id = None
_vault_id = None


def get_agent_id() -> str:
    global _agent_id
    if _agent_id is None:
        _agent_id = _require_env("AGENT_ID")
    return _agent_id


def get_environment_id() -> str:
    global _environment_id
    if _environment_id is None:
        _environment_id = _require_env("ENVIRONMENT_ID")
    return _environment_id


def get_vault_id() -> str:
    global _vault_id
    if _vault_id is None:
        _vault_id = _require_env("VAULT_ID")
    return _vault_id


# GCP config (safe defaults)
GCP_PROJECT = os.environ.get("GCP_PROJECT", "kanmonos-prod")
FIRESTORE_COLLECTION = os.environ.get("FIRESTORE_COLLECTION", "financing_clients")
