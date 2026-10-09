"""
JWT + password-hashing unit tests for `app.core.security`.

No I/O at all — pure functions over PyJWT/argon2-cffi. See
`tests/integration/test_auth_api.py` for these same primitives exercised
end-to-end through the HTTP layer.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    decode_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)

USER_ID = uuid.uuid4()
PLATFORM_ID = "divyang_matrimony"


class TestAccessToken:
    def test_encodes_expected_claims(self) -> None:
        token = create_access_token(user_id=USER_ID, platform_id=PLATFORM_ID, role=None)

        payload = decode_access_token(token)

        assert payload["sub"] == str(USER_ID)
        assert payload["platform"] == PLATFORM_ID
        assert payload["type"] == "access"
        assert payload["role"] is None
        assert payload["exp"] - payload["iat"] == settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

    def test_carries_admin_role(self) -> None:
        token = create_access_token(user_id=USER_ID, platform_id=PLATFORM_ID, role="ADMIN")

        payload = decode_access_token(token)

        assert payload["role"] == "ADMIN"

    def test_expired_token_raises(self) -> None:
        token = create_access_token(
            user_id=USER_ID,
            platform_id=PLATFORM_ID,
            expires_delta=timedelta(seconds=-1),
        )

        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_rejects_a_refresh_token(self) -> None:
        """`decode_access_token` must not accept a token minted as a refresh
        token, even though both share the same secret/algorithm."""
        refresh_token, _jti = create_refresh_token(user_id=USER_ID, platform_id=PLATFORM_ID)

        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(refresh_token)

    def test_tampered_signature_raises(self) -> None:
        token = create_access_token(user_id=USER_ID, platform_id=PLATFORM_ID)
        tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")

        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(tampered)

    def test_wrong_secret_key_is_rejected(self) -> None:
        token = jwt.encode(
            {"sub": str(USER_ID), "platform": PLATFORM_ID, "type": "access"},
            "a-completely-different-secret-key-value",
            algorithm=settings.JWT_ALGORITHM,
        )

        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(token)

    def test_garbage_input_raises(self) -> None:
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token("not-a-jwt-at-all")


class TestRefreshToken:
    def test_encodes_expected_claims_and_jti(self) -> None:
        token, jti = create_refresh_token(user_id=USER_ID, platform_id=PLATFORM_ID)

        payload = decode_refresh_token(token)

        assert payload["sub"] == str(USER_ID)
        assert payload["platform"] == PLATFORM_ID
        assert payload["type"] == "refresh"
        assert payload["jti"] == str(jti)
        assert payload["exp"] - payload["iat"] == settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400

    def test_each_call_gets_a_unique_jti(self) -> None:
        _token1, jti1 = create_refresh_token(user_id=USER_ID, platform_id=PLATFORM_ID)
        _token2, jti2 = create_refresh_token(user_id=USER_ID, platform_id=PLATFORM_ID)

        assert jti1 != jti2

    def test_explicit_jti_is_honored(self) -> None:
        """`refresh_tokens` rotation relies on being able to mint a token
        for a jti it already generated — verify the override path."""
        forced_jti = uuid.uuid4()

        token, returned_jti = create_refresh_token(
            user_id=USER_ID, platform_id=PLATFORM_ID, jti=forced_jti
        )

        assert returned_jti == forced_jti
        assert decode_refresh_token(token)["jti"] == str(forced_jti)

    def test_expired_token_raises(self) -> None:
        token, _jti = create_refresh_token(
            user_id=USER_ID, platform_id=PLATFORM_ID, expires_delta=timedelta(seconds=-1)
        )

        with pytest.raises(jwt.ExpiredSignatureError):
            decode_refresh_token(token)

    def test_rejects_an_access_token(self) -> None:
        access_token = create_access_token(user_id=USER_ID, platform_id=PLATFORM_ID)

        with pytest.raises(jwt.InvalidTokenError):
            decode_refresh_token(access_token)


class TestDecodeToken:
    """`decode_token` is the shared primitive — signature/expiry only, no
    `type` assertion (that's layered on by the access/refresh wrappers)."""

    def test_decodes_either_token_type(self) -> None:
        access_token = create_access_token(user_id=USER_ID, platform_id=PLATFORM_ID)
        refresh_token, _jti = create_refresh_token(user_id=USER_ID, platform_id=PLATFORM_ID)

        assert decode_token(access_token)["type"] == "access"
        assert decode_token(refresh_token)["type"] == "refresh"


class TestPasswordHashing:
    def test_verify_succeeds_for_correct_password(self) -> None:
        hashed = hash_password("CorrectHorseBattery1")

        assert verify_password("CorrectHorseBattery1", hashed) is True

    def test_verify_fails_for_wrong_password(self) -> None:
        hashed = hash_password("CorrectHorseBattery1")

        assert verify_password("WrongPassword1", hashed) is False

    def test_verify_never_raises_on_garbage_hash(self) -> None:
        """Architecture-mandated timing-safe behavior — `admin_login`
        deliberately verifies against a dummy hash for unknown emails and
        must never see an exception."""
        assert verify_password("anything", "not-a-real-argon2-hash") is False

    def test_hash_is_salted(self) -> None:
        """Two hashes of the same password must differ (random salt) yet
        both verify correctly."""
        first = hash_password("CorrectHorseBattery1")
        second = hash_password("CorrectHorseBattery1")

        assert first != second
        assert verify_password("CorrectHorseBattery1", first) is True
        assert verify_password("CorrectHorseBattery1", second) is True

    def test_fresh_hash_does_not_need_rehash(self) -> None:
        hashed = hash_password("CorrectHorseBattery1")

        assert password_needs_rehash(hashed) is False

    @pytest.mark.parametrize("password", ["", "a", "correct horse battery staple", "🔒🔑💾"])
    def test_round_trips_arbitrary_passwords(self, password: str) -> None:
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
