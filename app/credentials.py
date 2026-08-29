"""Password hashing (M2a): PBKDF2-SHA256 with a per-account salt, stdlib only.

Stored format: ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``.
Verification parses strictly and fails closed — any malformed stored string
is simply not a valid hash (returns False, never raises).
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 600_000
# Strict parse: algo, decimal iterations, then two hex strings of any length.
_PATTERN = re.compile(rf"^{_ALGO}\$(\d+)\$([0-9a-f]+)\$([0-9a-f]+)$")


def hash_password(password: str, iterations: int = _ITERATIONS) -> str:
    """Hash a password with a fresh random 16-byte salt (PBKDF2-SHA256)."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_ALGO}${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time compare of ``password`` against a stored hash string.

    Any malformed ``stored`` value returns False (never raises).
    """
    match = _PATTERN.fullmatch(stored)
    if match is None:
        return False
    iterations = int(match.group(1))
    salt = bytes.fromhex(match.group(2))
    expected = bytes.fromhex(match.group(3))
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def is_valid_password(password: str) -> bool:
    """A valid password is at least 8 characters."""
    return len(password) >= 8


def is_valid_email(email: str) -> bool:
    r"""Pragmatic email validation: matches ^[^@\s]+@[^@\s]+\.[^@\s]+$"""
    return re.fullmatch(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None
