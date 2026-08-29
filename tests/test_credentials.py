"""Password hashing (M2a): PBKDF2 round-trip, salt uniqueness, strict format.

``verify_password`` must fail closed (return False, never raise) on any malformed
stored string — a corrupted hash must not crash the login route.
"""

from app.credentials import hash_password, is_valid_email, is_valid_password, verify_password


def test_round_trip():
    stored = hash_password("testpass123")
    assert stored.startswith("pbkdf2_sha256$600000$")
    assert verify_password("testpass123", stored)


def test_wrong_password_rejected():
    stored = hash_password("testpass123")
    assert not verify_password("wrongpass", stored)


def test_malformed_stored_never_raises():
    malformed = [
        "",
        "plaintext",
        "pbkdf2_sha256$abc$ff$ff",  # non-numeric iterations
        "pbkdf2_sha256$600000$zz$zz",  # non-hex salt/hash
        "pbkdf2_sha256$600000$aa",  # missing hash segment
        "pbkdf2_sha256$600000$aa$bb$cc",  # extra segment
        "PBKDF2_SHA256$600000$aa$bb",  # wrong algorithm case
        "sha256$600000$aa$bb",  # wrong algorithm name
    ]
    for stored in malformed:
        assert verify_password("testpass123", stored) is False


def test_two_hashes_of_same_password_differ():
    """Per-account salt: identical passwords must produce different stored hashes."""
    assert hash_password("testpass123") != hash_password("testpass123")


def test_is_valid_password():
    assert is_valid_password("testpass123")
    assert is_valid_password("12345678")
    assert not is_valid_password("1234567")
    assert not is_valid_password("")
    assert not is_valid_password("short")


def test_is_valid_email():
    assert is_valid_email("test@example.com")
    assert is_valid_email("user.name+tag@example.co.uk")
    assert not is_valid_email("notanemail")
    assert not is_valid_email("@example.com")
    assert not is_valid_email("test@")
    assert not is_valid_email("")
    assert not is_valid_email("test @example.com")
    assert not is_valid_email("test@ example.com")
