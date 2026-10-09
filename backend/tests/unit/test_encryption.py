"""
Tests for app.core.encryption — AES-256-GCM field-level encryption.

Validates:
  - Round-trip: encrypt → decrypt returns original plaintext
  - None passthrough (nullable columns)
  - Different nonces per encrypt call (no deterministic ciphertext)
  - Tamper detection (GCM auth tag)
  - Bulk encrypt/decrypt helpers
"""
from __future__ import annotations

import base64

import pytest

from app.core.encryption import (
    ENCRYPTED_FIELDS,
    decrypt_field,
    decrypt_sensitive_dict,
    encrypt_field,
    encrypt_sensitive_dict,
)


class TestFieldEncryption:

    def test_round_trip_basic(self) -> None:
        plaintext = "Hello, Divyang Matrimony!"
        ciphertext = encrypt_field(plaintext)
        assert ciphertext is not None
        assert ciphertext != plaintext  # must be different from plaintext
        result = decrypt_field(ciphertext)
        assert result == plaintext

    def test_round_trip_unicode(self) -> None:
        """Encrypted fields may contain Devanagari or other scripts."""
        plaintext = "नमस्ते — मराठी 😀"
        ciphertext = encrypt_field(plaintext)
        assert decrypt_field(ciphertext) == plaintext

    def test_round_trip_empty_string(self) -> None:
        """Empty string is valid (distinct from None)."""
        ciphertext = encrypt_field("")
        assert decrypt_field(ciphertext) == ""

    def test_none_passthrough(self) -> None:
        assert encrypt_field(None) is None
        assert decrypt_field(None) is None

    def test_different_nonces(self) -> None:
        """Two encryptions of the same plaintext must produce different ciphertext."""
        plaintext = "+919876543210"
        c1 = encrypt_field(plaintext)
        c2 = encrypt_field(plaintext)
        assert c1 != c2  # different nonce each time
        # Both still decrypt to the same value
        assert decrypt_field(c1) == plaintext
        assert decrypt_field(c2) == plaintext

    def test_tamper_detection(self) -> None:
        """GCM must detect a flipped bit."""
        ciphertext_b64 = encrypt_field("secret data")
        assert ciphertext_b64 is not None
        raw = bytearray(base64.b64decode(ciphertext_b64))
        # Flip a byte in the ciphertext (past the 12-byte nonce)
        raw[15] ^= 0xFF
        tampered = base64.b64encode(bytes(raw)).decode("ascii")
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt_field(tampered)

    def test_invalid_base64(self) -> None:
        with pytest.raises(ValueError, match="Invalid base64"):
            decrypt_field("not-valid-base64!!!")

    def test_too_short(self) -> None:
        """Data shorter than nonce + GCM tag is invalid."""
        short = base64.b64encode(b"short").decode("ascii")
        with pytest.raises(ValueError, match="too short"):
            decrypt_field(short)

    def test_phone_number_round_trip(self) -> None:
        """contact_phone is a real use case — 10-digit Indian number."""
        phone = "+919876543210"
        ciphertext = encrypt_field(phone)
        assert ciphertext is not None
        # Ciphertext is much longer than 15 chars (proves VARCHAR(15) would fail)
        assert len(ciphertext) > 15
        assert decrypt_field(ciphertext) == phone


class TestBulkEncryption:

    def test_encrypt_sensitive_dict(self) -> None:
        data = {
            "religion": "Hindu",  # not encrypted
            "contact_phone": "+919876543210",  # encrypted
            "disability_details": "Uses wheelchair",  # encrypted
            "disability_percentage": 75,  # not encrypted
        }
        encrypted = encrypt_sensitive_dict(data)

        # Non-encrypted fields pass through
        assert encrypted["religion"] == "Hindu"
        assert encrypted["disability_percentage"] == 75

        # Encrypted fields are transformed
        assert encrypted["contact_phone"] != "+919876543210"
        assert encrypted["disability_details"] != "Uses wheelchair"

        # Round-trip
        decrypted = decrypt_sensitive_dict(encrypted)
        assert decrypted["contact_phone"] == "+919876543210"
        assert decrypted["disability_details"] == "Uses wheelchair"
        assert decrypted["religion"] == "Hindu"

    def test_none_values_in_bulk(self) -> None:
        data = {
            "contact_phone": None,
            "religion": "Sikh",
        }
        encrypted = encrypt_sensitive_dict(data)
        assert encrypted["contact_phone"] is None
        assert encrypted["religion"] == "Sikh"

    def test_encrypted_fields_constant(self) -> None:
        """The set of encrypted fields matches Database.md §3.3."""
        assert {
            "disability_details",
            "health_conditions",
            "about_family",
            "contact_phone",
            "contact_email",
            "whatsapp_number",
        } == ENCRYPTED_FIELDS
