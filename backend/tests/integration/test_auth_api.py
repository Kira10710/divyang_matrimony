"""
API endpoint tests for `app/api/v1/auth.py`.

Exercises the real FastAPI app — routing, middleware, exception handlers,
the real `AuthService`/repositories — over HTTP via `TestClient`. Only two
things are faked: the database (in-memory SQLite, see `tests/conftest.py`)
and Redis (`FakeRedis`, backing a real `RedisOtpService`). Everything else
is the genuine request path a real client would go through.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_refresh_token

from ..fakes import FakeRedis
from ..support import PHONE, PLATFORM, auth_headers, decode_jti, get_otp_code, login, wrong_code


class TestSendOtp:
    def test_valid_phone_returns_200(self, app_client: TestClient) -> None:
        response = app_client.post("/api/v1/auth/send-otp", json={"phone": "9876543210"})

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

    def test_accepts_e164_format_too(self, app_client: TestClient) -> None:
        response = app_client.post("/api/v1/auth/send-otp", json={"phone": PHONE})

        assert response.status_code == 200

    @pytest.mark.parametrize("bad_phone", ["12345", "not-a-phone", "+1234567890123456", "98765"])
    def test_invalid_phone_format_is_rejected(self, app_client: TestClient, bad_phone: str) -> None:
        response = app_client.post("/api/v1/auth/send-otp", json={"phone": bad_phone})

        assert response.status_code == 422
        body = response.json()
        assert body["success"] is False
        assert body["errors"]

    def test_banned_account_is_rejected(self, app_client: TestClient, make_user) -> None:
        asyncio.run(make_user(phone=PHONE, is_banned=True))

        response = app_client.post("/api/v1/auth/send-otp", json={"phone": PHONE})

        assert response.status_code == 403
        assert response.json()["errors"][0]["code"] == "ACCOUNT_BANNED"


class TestVerifyOtp:
    def test_correct_code_creates_a_new_user(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        data = login(app_client, fake_redis, device_info="pytest-device")

        assert data["is_new_user"] is True
        assert data["user"]["phone"] == PHONE
        assert data["tokens"]["access_token"]
        assert data["tokens"]["refresh_token"]
        assert data["tokens"]["token_type"] == "Bearer"

    def test_returning_user_is_not_flagged_as_new(
        self, app_client: TestClient, fake_redis: FakeRedis, make_user
    ) -> None:
        asyncio.run(make_user(phone=PHONE))

        data = login(app_client, fake_redis)

        assert data["is_new_user"] is False

    def test_new_user_is_then_visible_via_me(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        data = login(app_client, fake_redis)

        response = app_client.get("/api/v1/auth/me", headers=auth_headers(data["tokens"]["access_token"]))

        assert response.status_code == 200
        assert response.json()["data"]["phone"] == PHONE

    def test_wrong_code_is_rejected(self, app_client: TestClient, fake_redis: FakeRedis) -> None:
        app_client.post("/api/v1/auth/send-otp", json={"phone": PHONE})
        code = get_otp_code(fake_redis, PHONE)

        response = app_client.post(
            "/api/v1/auth/verify-otp", json={"phone": PHONE, "otp": wrong_code(code)}
        )

        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "OTP_INVALID"

    def test_code_for_a_never_requested_phone_is_rejected(self, app_client: TestClient) -> None:
        response = app_client.post(
            "/api/v1/auth/verify-otp", json={"phone": PHONE, "otp": "123456"}
        )

        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "OTP_INVALID"

    def test_banned_user_is_rejected_even_with_the_correct_code(
        self, app_client: TestClient, fake_redis: FakeRedis, make_user, db_session_factory
    ) -> None:
        # `send_otp` itself already refuses banned accounts (see
        # `test_banned_account_is_rejected` above), so reaching `verify_otp`'s
        # own (redundant, defense-in-depth) ban check requires the account to
        # go from OK -> banned *after* the OTP was already sent — e.g. a ban
        # applied in the window between requesting and entering the code.
        user_row = asyncio.run(make_user(phone=PHONE, is_banned=False))
        app_client.post("/api/v1/auth/send-otp", json={"phone": PHONE})
        code = get_otp_code(fake_redis, PHONE)

        async def _ban() -> None:
            from app.repositories.user_repository import UserRepository

            async with db_session_factory() as session:
                repo = UserRepository(session)
                user = await repo.get_by_id(user_row.id)
                assert user is not None
                await repo.update(user, {"is_banned": True})
                await session.commit()

        asyncio.run(_ban())

        response = app_client.post("/api/v1/auth/verify-otp", json={"phone": PHONE, "otp": code})

        assert response.status_code == 403
        assert response.json()["errors"][0]["code"] == "ACCOUNT_BANNED"

    def test_inactive_user_is_rejected(
        self, app_client: TestClient, fake_redis: FakeRedis, make_user
    ) -> None:
        asyncio.run(make_user(phone=PHONE, is_active=False))
        app_client.post("/api/v1/auth/send-otp", json={"phone": PHONE})
        code = get_otp_code(fake_redis, PHONE)

        response = app_client.post("/api/v1/auth/verify-otp", json={"phone": PHONE, "otp": code})

        assert response.status_code == 401

    def test_account_locks_after_repeated_wrong_codes(
        self,
        app_client: TestClient,
        fake_redis: FakeRedis,
        make_user,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "AUTH_MAX_FAILED_ATTEMPTS", 2)
        asyncio.run(make_user(phone=PHONE))
        app_client.post("/api/v1/auth/send-otp", json={"phone": PHONE})
        code = get_otp_code(fake_redis, PHONE)
        wrong = wrong_code(code)

        for _ in range(2):
            response = app_client.post("/api/v1/auth/verify-otp", json={"phone": PHONE, "otp": wrong})
            assert response.status_code == 400

        locked_response = app_client.post(
            "/api/v1/auth/verify-otp", json={"phone": PHONE, "otp": wrong}
        )

        assert locked_response.status_code == 401
        assert locked_response.json()["errors"][0]["code"] == "ACCOUNT_LOCKED"

    def test_missing_otp_field_is_a_validation_error(self, app_client: TestClient) -> None:
        response = app_client.post("/api/v1/auth/verify-otp", json={"phone": PHONE})

        assert response.status_code == 422


class TestAdminLogin:
    EMAIL = "admin@divyangmatrimony.com"
    PASSWORD = "CorrectHorseBattery1"

    def test_correct_credentials_succeed(self, app_client: TestClient, make_admin) -> None:
        asyncio.run(make_admin(email=self.EMAIL, password=self.PASSWORD))

        response = app_client.post(
            "/api/v1/auth/login-admin",
            json={"email": self.EMAIL, "password": self.PASSWORD},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["user"]["role"] == "ADMIN"
        assert data["tokens"]["access_token"]

    def test_wrong_password_is_rejected(self, app_client: TestClient, make_admin) -> None:
        asyncio.run(make_admin(email=self.EMAIL, password=self.PASSWORD))

        response = app_client.post(
            "/api/v1/auth/login-admin",
            json={"email": self.EMAIL, "password": "WrongPassword1"},
        )

        assert response.status_code == 401

    def test_unknown_email_is_rejected(self, app_client: TestClient) -> None:
        response = app_client.post(
            "/api/v1/auth/login-admin",
            json={"email": "nobody@divyangmatrimony.com", "password": self.PASSWORD},
        )

        assert response.status_code == 401

    def test_non_admin_account_with_matching_email_is_rejected(
        self, app_client: TestClient, make_user
    ) -> None:
        asyncio.run(make_user(phone=PHONE, email=self.EMAIL, role=None))

        response = app_client.post(
            "/api/v1/auth/login-admin",
            json={"email": self.EMAIL, "password": self.PASSWORD},
        )

        assert response.status_code == 401

    def test_banned_admin_is_rejected(self, app_client: TestClient, make_admin) -> None:
        asyncio.run(make_admin(email=self.EMAIL, password=self.PASSWORD, is_banned=True))

        response = app_client.post(
            "/api/v1/auth/login-admin",
            json={"email": self.EMAIL, "password": self.PASSWORD},
        )

        assert response.status_code == 403

    def test_short_password_is_a_validation_error(self, app_client: TestClient) -> None:
        response = app_client.post(
            "/api/v1/auth/login-admin",
            json={"email": self.EMAIL, "password": "short"},
        )

        assert response.status_code == 422


class TestRefresh:
    def test_rotates_the_token_pair(self, app_client: TestClient, fake_redis: FakeRedis) -> None:
        login_data = login(app_client, fake_redis)

        response = app_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": login_data["tokens"]["refresh_token"]}
        )

        assert response.status_code == 200
        new_tokens = response.json()["data"]
        # Refresh tokens carry a unique `jti` and are always distinct. Access
        # tokens carry no nonce, so two minted in the same wall-clock second
        # for the same user/role can be byte-identical — that's expected,
        # not a bug, so it isn't asserted on here.
        assert new_tokens["refresh_token"] != login_data["tokens"]["refresh_token"]

    def test_a_rotated_refresh_token_cannot_be_reused(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        login_data = login(app_client, fake_redis)
        old_refresh_token = login_data["tokens"]["refresh_token"]
        app_client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh_token})

        reuse_response = app_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": old_refresh_token}
        )

        assert reuse_response.status_code == 401

    def test_malformed_token_is_rejected(self, app_client: TestClient) -> None:
        response = app_client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-jwt"})

        assert response.status_code == 401
        assert response.json()["errors"][0]["code"] == "INVALID_TOKEN"

    def test_expired_token_is_rejected(self, app_client: TestClient) -> None:
        token, _jti = create_refresh_token(
            user_id=uuid.uuid4(), platform_id=PLATFORM, expires_delta=timedelta(seconds=-1)
        )

        response = app_client.post("/api/v1/auth/refresh", json={"refresh_token": token})

        assert response.status_code == 401
        assert response.json()["errors"][0]["code"] == "TOKEN_EXPIRED"

    def test_unknown_session_is_rejected(self, app_client: TestClient) -> None:
        """A syntactically valid, signed refresh token whose session row was
        never created (e.g. the server's secret leaked and someone forged
        one) must still be rejected — Architecture §7.7's stateful check."""
        token, _jti = create_refresh_token(user_id=uuid.uuid4(), platform_id=PLATFORM)

        response = app_client.post("/api/v1/auth/refresh", json={"refresh_token": token})

        assert response.status_code == 401


class TestLogout:
    def test_logs_out_the_current_device(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        login_data = login(app_client, fake_redis)

        response = app_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": login_data["tokens"]["refresh_token"]},
            headers=auth_headers(login_data["tokens"]["access_token"]),
        )

        assert response.status_code == 200

    def test_logged_out_refresh_token_can_no_longer_be_used(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        login_data = login(app_client, fake_redis)
        app_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": login_data["tokens"]["refresh_token"]},
            headers=auth_headers(login_data["tokens"]["access_token"]),
        )

        response = app_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": login_data["tokens"]["refresh_token"]}
        )

        assert response.status_code == 401

    def test_requires_authentication(self, app_client: TestClient) -> None:
        response = app_client.post("/api/v1/auth/logout", json={"refresh_token": "irrelevant"})

        assert response.status_code == 401


class TestLogoutAll:
    def test_revokes_every_session_for_the_user(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        first = login(app_client, fake_redis)
        second = login(app_client, fake_redis)  # second "device" login, same phone

        response = app_client.post(
            "/api/v1/auth/logout-all", headers=auth_headers(second["tokens"]["access_token"])
        )

        assert response.status_code == 200
        assert response.json()["data"]["revoked_sessions"] == 2

        sessions_response = app_client.get(
            "/api/v1/auth/sessions", headers=auth_headers(first["tokens"]["access_token"])
        )
        assert sessions_response.json()["data"]["sessions"] == []

    def test_requires_authentication(self, app_client: TestClient) -> None:
        response = app_client.post("/api/v1/auth/logout-all")

        assert response.status_code == 401


class TestSessions:
    def test_lists_the_active_session(self, app_client: TestClient, fake_redis: FakeRedis) -> None:
        login_data = login(app_client, fake_redis, device_info="Pixel 7")

        response = app_client.get(
            "/api/v1/auth/sessions", headers=auth_headers(login_data["tokens"]["access_token"])
        )

        assert response.status_code == 200
        body = response.json()["data"]
        assert body["total"] == 1
        assert body["sessions"][0]["device_info"] == "Pixel 7"

    def test_marks_the_requesting_session_as_current(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        login_data = login(app_client, fake_redis)
        jti = decode_jti(login_data["tokens"]["refresh_token"])

        response = app_client.get(
            "/api/v1/auth/sessions",
            headers={**auth_headers(login_data["tokens"]["access_token"]), "X-Session-JTI": jti},
        )

        assert response.json()["data"]["sessions"][0]["is_current"] is True

    def test_without_the_jti_header_nothing_is_marked_current(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        login_data = login(app_client, fake_redis)

        response = app_client.get(
            "/api/v1/auth/sessions", headers=auth_headers(login_data["tokens"]["access_token"])
        )

        assert response.json()["data"]["sessions"][0]["is_current"] is False

    def test_requires_authentication(self, app_client: TestClient) -> None:
        response = app_client.get("/api/v1/auth/sessions")

        assert response.status_code == 401


class TestMe:
    def test_returns_the_authenticated_user(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        login_data = login(app_client, fake_redis)

        response = app_client.get(
            "/api/v1/auth/me", headers=auth_headers(login_data["tokens"]["access_token"])
        )

        assert response.status_code == 200
        assert response.json()["data"]["phone"] == PHONE

    def test_requires_authentication(self, app_client: TestClient) -> None:
        response = app_client.get("/api/v1/auth/me")

        assert response.status_code == 401

    def test_rejects_a_garbage_token(self, app_client: TestClient) -> None:
        response = app_client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
        )

        assert response.status_code == 401

    def test_rejects_an_expired_token(self, app_client: TestClient) -> None:
        from app.core.security import create_access_token

        token = create_access_token(
            user_id=uuid.uuid4(), platform_id=PLATFORM, expires_delta=timedelta(seconds=-1)
        )

        response = app_client.get("/api/v1/auth/me", headers=auth_headers(token))

        assert response.status_code == 401
