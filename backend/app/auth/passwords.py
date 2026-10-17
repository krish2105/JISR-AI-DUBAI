"""
passwords.py — Password hashing with scrypt (Python standard library, no extra dependency).

Stored form: "scrypt$<n>$<r>$<p>$<salt b64>$<hash b64>". A memory-hard function makes stolen hashes expensive to
crack; the parameters travel with each hash so they can be raised later without breaking old passwords.
"""

import base64
import hashlib
import hmac
import secrets

N, R, P, DKLEN = 2**14, 8, 1, 32
MIN_LENGTH = 10


class WeakPassword(ValueError):
    """The password does not meet the minimum rules."""


def check_strength(password: str) -> None:
    """Minimum rules: 10+ characters, not all one character class of digits."""
    if len(password) < MIN_LENGTH:
        raise WeakPassword(f"Use at least {MIN_LENGTH} characters.")
    if password.isdigit():
        raise WeakPassword("Use letters as well as digits.")


def hash_password(password: str) -> str:
    """Hash a password with a fresh random salt."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=N, r=R, p=P, dklen=DKLEN)
    b64 = lambda b: base64.b64encode(b).decode("ascii")  # noqa: E731
    return f"scrypt${N}${R}${P}${b64(salt)}${b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time check of a password against a stored hash (False for malformed or missing hashes)."""
    if not stored:
        return False
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(hash_b64)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt_b64), n=int(n), r=int(r),
                                p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)


# A fixed hash compared against when the email is unknown, so a login takes the same time either way.
DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")
