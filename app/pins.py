"""PIN hashing (D2/D16): PBKDF2-SHA256 with a per-person salt, stdlib only.

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
_ITERATIONS = 200_000
# Strict parse: algo, decimal iterations, then two hex strings of any length.
_PATTERN = re.compile(rf"^{_ALGO}\$(\d+)\$([0-9a-f]+)\$([0-9a-f]+)$")


def hash_pin(pin: str, iterations: int = _ITERATIONS) -> str:
    """Hash a 4-digit PIN with a fresh random 16-byte salt (PBKDF2-SHA256)."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations)
    return f"{_ALGO}${iterations}${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    """Constant-time compare of ``pin`` against a stored hash string.

    Any malformed ``stored`` value returns False (never raises).
    """
    match = _PATTERN.fullmatch(stored)
    if match is None:
        return False
    iterations = int(match.group(1))
    salt = bytes.fromhex(match.group(2))
    expected = bytes.fromhex(match.group(3))
    actual = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def is_valid_pin(pin: str) -> bool:
    """A valid household PIN is exactly four ASCII digits."""
    return re.fullmatch(r"\d{4}", pin) is not None
