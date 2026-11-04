"""Symmetric encryption for tokens at rest and for the short-lived OAuth transaction cookie."""

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

__all__ = ["InvalidToken", "decrypt", "encrypt"]


def _fernet() -> Fernet:
    return Fernet(get_settings().token_encryption_key.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str, ttl: int | None = None) -> str:
    """Raises InvalidToken if tampered with, or older than `ttl` seconds when given."""
    return _fernet().decrypt(ciphertext.encode(), ttl=ttl).decode()
