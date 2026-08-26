"""PIN hashing (D2): PBKDF2 round-trip, salt uniqueness, strict format.

``verify_pin`` must fail closed (return False, never raise) on any malformed
stored string — a corrupted hash must not crash the login route.
"""

from app.pins import hash_pin, is_valid_pin, verify_pin


def test_round_trip():
    stored = hash_pin("1234")
    assert stored.startswith("pbkdf2_sha256$200000$")
    assert verify_pin("1234", stored)


def test_wrong_pin_rejected():
    stored = hash_pin("1234")
    assert not verify_pin("9999", stored)


def test_malformed_stored_never_raises():
    malformed = [
        "",
        "plaintext",
        "pbkdf2_sha256$abc$ff$ff",  # non-numeric iterations
        "pbkdf2_sha256$200000$zz$zz",  # non-hex salt/hash
        "pbkdf2_sha256$200000$aa",  # missing hash segment
        "pbkdf2_sha256$200000$aa$bb$cc",  # extra segment
        "PBKDF2_SHA256$200000$aa$bb",  # wrong algorithm case
        "sha256$200000$aa$bb",  # wrong algorithm name
    ]
    for stored in malformed:
        assert verify_pin("1234", stored) is False


def test_two_hashes_of_same_pin_differ():
    """Per-person salt: identical PINs must produce different stored hashes."""
    assert hash_pin("1234") != hash_pin("1234")


def test_is_valid_pin():
    assert is_valid_pin("1234")
    assert not is_valid_pin("123")
    assert not is_valid_pin("12a4")
    assert not is_valid_pin("abcd")
    assert not is_valid_pin("")
