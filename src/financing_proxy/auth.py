"""API key generation, hashing, and validation.

Keys use a fin_ prefix for easy identification.
Only the hash is stored — the plaintext key is returned once at registration.
Lookup uses a prefix index for fast Firestore queries.
"""

import hashlib
import secrets

KEY_PREFIX = "fin_"
KEY_BYTES = 32  # 32 bytes = 43 chars in URL-safe base64
PREFIX_LENGTH = 8  # first 8 chars stored for fast lookup


def generate_api_key() -> str:
    """Generate a new API key with fin_ prefix."""
    raw = secrets.token_urlsafe(KEY_BYTES)
    return f"{KEY_PREFIX}{raw}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage. Uses SHA-256."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_key_prefix(api_key: str) -> str:
    """Extract the prefix used for fast Firestore lookup."""
    return api_key[:PREFIX_LENGTH]
