"""Per-group API token helpers (M6a, plan §8 M6): generation + hashing.

Tokens are 256-bit random values (``secrets.token_urlsafe(32)``). Because
they are high-entropy, they are hashed with SHA-256 — NOT PBKDF2, which is
for low-entropy passwords; a fast hash is correct and standard for random
tokens. Only the hash is ever stored; the plaintext is shown to the group
owner exactly once at generation.

Pure module: no database access.
"""

from __future__ import annotations

import hashlib
import secrets


def generate_token() -> str:
    """A fresh 256-bit URL-safe token — the plaintext shown to the owner once."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 hex digest of a token — what the DB stores, never the plaintext."""
    return hashlib.sha256(token.encode()).hexdigest()
