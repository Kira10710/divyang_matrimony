"""
Field-level AES-256-GCM encryption for sensitive profile data.

Architecture §5.2, Database.md §3.3: encrypted columns store base64-encoded
ciphertext (nonce || tag || ciphertext) as TEXT.

The encryption key is loaded from environment variables, never stored in
the database. Key rotation requires re-encrypting all rows — a migration
script, not a config change.

Design:
  - encrypt(plaintext) → base64 string (safe for TEXT column storage)
  - decrypt(ciphertext_b64) → plaintext string
  - Both return None for None input (nullable columns)
  - decrypt raises ValueError on tampered/corrupted data (GCM auth tag check)
"""
import base64
import os
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

# AES-256 requires a 32-byte key.
_NONCE_LENGTH = 12  # GCM standard: 96-bit nonce


@lru_cache(maxsize=1)
def _get_cipher() -> AESGCM:
    """
    Lazily initialise the AES-GCM cipher from the env var.

    The key is hex-encoded in the environment variable (64 hex chars = 32 bytes).
    Cached so the key is parsed exactly once per process lifetime.
    """
    key_hex = settings.FIELD_ENCRYPTION_KEY
    key_bytes = bytes.fromhex(key_hex)
    if len(key_bytes) != 32:
        raise ValueError(
            f"FIELD_ENCRYPTION_KEY must be exactly 32 bytes (64 hex chars), "
            f"got {len(key_bytes)} bytes."
        )
    return AESGCM(key_bytes)


def encrypt_field(plaintext: str | None) -> str | None:
    """
    Encrypt a plaintext string for storage in a TEXT column.

    Returns base64-encoded (nonce || ciphertext_with_tag).
    Returns None if plaintext is None (nullable column passthrough).
    """
    if plaintext is None:
        return None

    cipher = _get_cipher()
    nonce = os.urandom(_NONCE_LENGTH)
    ciphertext = cipher.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Store as: nonce (12 bytes) || ciphertext+tag
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_field(ciphertext_b64: str | None) -> str | None:
    """
    Decrypt a base64-encoded ciphertext back to plaintext.

    Returns None if ciphertext_b64 is None (nullable column passthrough).
    Raises ValueError if the data is corrupted or the auth tag fails
    (GCM guarantees tamper detection).
    """
    if ciphertext_b64 is None:
        return None

    try:
        raw = base64.b64decode(ciphertext_b64)
    except Exception as exc:
        raise ValueError(f"Invalid base64 in encrypted field: {exc}") from exc

    if len(raw) < _NONCE_LENGTH + 16:
        raise ValueError(
            "Encrypted data too short — missing nonce or GCM auth tag."
        )

    nonce = raw[:_NONCE_LENGTH]
    ciphertext = raw[_NONCE_LENGTH:]

    cipher = _get_cipher()
    try:
        plaintext_bytes = cipher.decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise ValueError(f"Decryption failed (corrupted or wrong key): {exc}") from exc

    return plaintext_bytes.decode("utf-8")


# --- Bulk helpers for the service layer ---

# The 6 fields that are encrypted in sensitive_profile_data (Database.md §3.3)
ENCRYPTED_FIELDS: frozenset[str] = frozenset({
    "disability_details",
    "health_conditions",
    "about_family",
    "contact_phone",
    "contact_email",
    "whatsapp_number",
})


def encrypt_sensitive_dict(data: dict) -> dict:
    """
    Encrypt all ENCRYPTED_FIELDS present in `data`.

    Non-encrypted fields pass through unchanged.
    Used by the service before writing to the repository.
    """
    result = dict(data)
    for field in ENCRYPTED_FIELDS:
        if field in result and result[field] is not None:
            result[field] = encrypt_field(result[field])
    return result


def decrypt_sensitive_dict(data: dict) -> dict:
    """
    Decrypt all ENCRYPTED_FIELDS present in `data`.

    Non-encrypted fields pass through unchanged.
    Used by the service after reading from the repository.
    """
    result = dict(data)
    for field in ENCRYPTED_FIELDS:
        if field in result and result[field] is not None:
            result[field] = decrypt_field(result[field])
    return result
