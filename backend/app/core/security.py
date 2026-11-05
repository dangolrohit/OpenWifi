"""Security, Argon2id hashing, and session authentication utilities."""
import hmac
import secrets
from typing import Optional
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16
)

def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return hasher.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2id hash."""
    try:
        return hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False

def generate_session_token() -> str:
    """Generate a high-entropy URL-safe session token."""
    return secrets.token_urlsafe(32)

def generate_csrf_token() -> str:
    """Generate a CSRF token."""
    return secrets.token_hex(16)

def generate_voucher_code(length: int = 6) -> str:
    """Generate numeric voucher code."""
    return "".join(secrets.choice("0123456789") for _ in range(length))

