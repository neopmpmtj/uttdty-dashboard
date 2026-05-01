"""Encrypt Google OAuth secrets at rest using Fernet(MASTER_ENCRYPTION_KEY)."""

from functools import lru_cache
from typing import Optional, Union

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _key_bytes(master_key: Union[str, bytes]) -> bytes:
    if isinstance(master_key, bytes):
        return master_key
    return master_key.encode("utf-8")


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = getattr(settings, "MASTER_ENCRYPTION_KEY", None)
    if not key:
        raise ValueError("MASTER_ENCRYPTION_KEY is not configured")
    return Fernet(_key_bytes(key))


def encrypt_value(value: str) -> str:
    if value is None:
        raise ValueError("value cannot be None")
    if not isinstance(value, str):
        value = str(value)
    token = _fernet().encrypt(value.encode("utf-8"))
    return token.decode("ascii")


def decrypt_value(encrypted_value: str) -> Optional[str]:
    if not encrypted_value:
        return None
    try:
        return _fernet().decrypt(encrypted_value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError):
        return None
