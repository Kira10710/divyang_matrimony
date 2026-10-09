"""
Service tests for `app.services.auth_service.AuthService`.

Fully isolated from I/O: `IUserRepository`/`ISessionRepository`/`IOtpService`
are all `AsyncMock`s built with `spec=` (so a typo'd method name fails the
test instead of silently returning a fresh `Mock`). Real, unpersisted
`User`/`ActiveSession` instances stand in for whatever the mocked
repositories would have loaded — this exercises `AuthService`'s own
branching logic without needing a database at all.

See `tests/repositories/` for the repositories' own persistence behavior,
and `tests/integration/test_auth_api.py` for all of this wired together
through real HTTP requests.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

import app.services.auth_service as auth_service_module
from app.core.exceptions import (
    AccountBannedError,
    AccountLockedError,
    InvalidTokenError,
    OtpError,
    TokenExpiredError,
    UnauthorizedError,
)
from app.core.security import create_refresh_token, hash_password
from app.models.active_session import ActiveSession
from app.models.login_history import LoginEventTypeEnum
from app.models.user import AdminRoleEnum, User
from app.repositories.session_repository import ISessionRepository
from app.repositories.user_repository import IUserRepository
from app.services.auth_service import AuthService
from app.services.otp_service import IOtpService, RedisOtpService

PLATFORM = "divyang_matrimony"
PHONE = "+919876543210"


def _build_user(**overrides: object) -> User:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "phone": PHONE,
        "email": None,
        "role": None,
        "platform_id": PLATFORM,
        "password_hash": None,
        "is_active": True,
        "is_banned": False,
        "is_phone_verified": True,
        "is_email_verified": False,
        "fcm_token": None,
        "last_login_at": None,
        "created_at": datetime.now(UTC),
        "deleted_at": None,
    }
    defaults.update(overrides)
    return User(**defaults)


def _build_session(**overrides: object) -> ActiveSession:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "refresh_token_jti": str(uuid.uuid4()),
        "device_info": "Pixel 7",
        "ip_address": "127.0.0.1",
        "expires_at": datetime.now(UTC) + timedelta(days=30),
        "last_used_at": None,
        "is_revoked": False,
        "revoked_at": None,
        "platform_id": PLATFORM,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return ActiveSession(**defaults)


@pytest.fixture
def mock_user_repo() -> AsyncMock:
    return AsyncMock(spec=IUserRepository)


@pytest.fixture
def mock_session_repo() -> AsyncMock:
    mock = AsyncMock(spec=ISessionRepository)
    mock.list_active_sessions.return_value = []
    return mock


@pytest.fixture
def mock_otp_service() -> AsyncMock:
    return AsyncMock(spec=IOtpService)


@pytest.fixture
def auth_service(
    mock_user_repo: AsyncMock, mock_session_repo: AsyncMock, mock_otp_service: AsyncMock
) -> AuthService:
    return AuthService(mock_user_repo, mock_session_repo, mock_otp_service)


class TestSendOtp:
    async def test_delegates_to_otp_service_for_a_fresh_phone(
        self, auth_service: AuthService, mock_user_repo: AsyncMock, mock_otp_service: AsyncMock
    ) -> None:
        mock_user_repo.get_by_phone.return_value = None

        await auth_service.send_otp(PHONE, PLATFORM)

        mock_otp_service.send_otp.assert_awaited_once_with(PHONE, PLATFORM)

    async def test_delegates_for_an_existing_unbanned_user(
        self, auth_service: AuthService, mock_user_repo: AsyncMock, mock_otp_service: AsyncMock
    ) -> None:
        mock_user_repo.get_by_phone.return_value = _build_user()

        await auth_service.send_otp(PHONE, PLATFORM)

        mock_otp_service.send_otp.assert_awaited_once_with(PHONE, PLATFORM)

    async def test_banned_user_is_rejected_before_sending(
        self, auth_service: AuthService, mock_user_repo: AsyncMock, mock_otp_service: AsyncMock
    ) -> None:
        mock_user_repo.get_by_phone.return_value = _build_user(is_banned=True)

        with pytest.raises(AccountBannedError):
            await auth_service.send_otp(PHONE, PLATFORM)

        mock_otp_service.send_otp.assert_not_awaited()


class TestVerifyOtp:
    async def test_wrong_otp_raises_and_logs_nothing_for_an_unknown_phone(
        self,
        auth_service: AuthService,
        mock_user_repo: AsyncMock,
        mock_session_repo: AsyncMock,
        mock_otp_service: AsyncMock,
    ) -> None:
        mock_otp_service.verify_otp.return_value = False
        mock_user_repo.get_by_phone.return_value = None

        with pytest.raises(OtpError):
            await auth_service.verify_otp(PHONE, "000000", PLATFORM)

        mock_session_repo.log_event.assert_not_awaited()

    async def test_wrong_otp_for_a_known_phone_logs_a_failed_attempt(
        self,
        auth_service: AuthService,
        mock_user_repo: AsyncMock,
        mock_session_repo: AsyncMock,
        mock_otp_service: AsyncMock,
    ) -> None:
        existing = _build_user()
        mock_otp_service.verify_otp.return_value = False
        mock_user_repo.get_by_phone.return_value = existing

        with pytest.raises(OtpError):
            await auth_service.verify_otp(PHONE, "000000", PLATFORM)

        mock_session_repo.log_event.assert_awaited_once()
        assert mock_session_repo.log_event.await_args.kwargs["event_type"] == LoginEventTypeEnum.LOGIN_FAILED
        assert mock_session_repo.log_event.await_args.kwargs["user_id"] == existing.id

    async def test_account_locked_short_circuits_before_verifying(
        self, mock_user_repo: AsyncMock, mock_session_repo: AsyncMock
    ) -> None:
        # Must be spec'd on RedisOtpService specifically — AuthService only
        # runs the lockout check `isinstance(self._otp_service, RedisOtpService)`.
        locked_otp = AsyncMock(spec=RedisOtpService)
        locked_otp.is_account_locked.return_value = True
        service = AuthService(mock_user_repo, mock_session_repo, locked_otp)

        with pytest.raises(AccountLockedError):
            await service.verify_otp(PHONE, "000000", PLATFORM)

        locked_otp.verify_otp.assert_not_awaited()

    async def test_console_otp_service_is_never_subject_to_the_lockout_check(
        self, auth_service: AuthService, mock_user_repo: AsyncMock, mock_otp_service: AsyncMock
    ) -> None:
        """`mock_otp_service` is spec'd on the bare `IOtpService` interface —
        confirms the lockout branch is skipped (not crashed on) for any OTP
        service that doesn't implement it, matching `ConsoleOtpService`."""
        mock_otp_service.verify_otp.return_value = True
        mock_user_repo.get_by_phone.return_value = _build_user()

        await auth_service.verify_otp(PHONE, "000000", PLATFORM)  # must not raise

    async def test_correct_otp_creates_a_new_user(
        self,
        auth_service: AuthService,
        mock_user_repo: AsyncMock,
        mock_session_repo: AsyncMock,
        mock_otp_service: AsyncMock,
    ) -> None:
        mock_otp_service.verify_otp.return_value = True
        mock_user_repo.get_by_phone.return_value = None
        created = _build_user()
        mock_user_repo.create.return_value = created

        result = await auth_service.verify_otp(PHONE, "000000", PLATFORM, device_info="Pixel 7")

        assert result.is_new_user is True
        assert result.user.id == created.id
        assert result.tokens.access_token
        assert result.tokens.refresh_token
        mock_otp_service.invalidate_otp.assert_awaited_once_with(PHONE, PLATFORM)
        mock_session_repo.create_session.assert_awaited_once()
        mock_user_repo.update_last_login.assert_awaited_once()

    async def test_correct_otp_for_an_existing_user_does_not_create_one(
        self,
        auth_service: AuthService,
        mock_user_repo: AsyncMock,
        mock_otp_service: AsyncMock,
    ) -> None:
        mock_otp_service.verify_otp.return_value = True
        mock_user_repo.get_by_phone.return_value = _build_user()

        result = await auth_service.verify_otp(PHONE, "000000", PLATFORM)

        assert result.is_new_user is False
        mock_user_repo.create.assert_not_awaited()

    async def test_marks_phone_verified_if_it_was_not_already(
        self, auth_service: AuthService, mock_user_repo: AsyncMock, mock_otp_service: AsyncMock
    ) -> None:
        mock_otp_service.verify_otp.return_value = True
        mock_user_repo.get_by_phone.return_value = _build_user(is_phone_verified=False)

        await auth_service.verify_otp(PHONE, "000000", PLATFORM)

        mock_user_repo.update_phone_verified.assert_awaited_once()

    async def test_banned_existing_user_is_rejected(
        self, auth_service: AuthService, mock_user_repo: AsyncMock, mock_otp_service: AsyncMock
    ) -> None:
        mock_otp_service.verify_otp.return_value = True
        mock_user_repo.get_by_phone.return_value = _build_user(is_banned=True)

        with pytest.raises(AccountBannedError):
            await auth_service.verify_otp(PHONE, "000000", PLATFORM)

    async def test_inactive_existing_user_is_rejected(
        self, auth_service: AuthService, mock_user_repo: AsyncMock, mock_otp_service: AsyncMock
    ) -> None:
        mock_otp_service.verify_otp.return_value = True
        mock_user_repo.get_by_phone.return_value = _build_user(is_active=False)

        with pytest.raises(UnauthorizedError):
            await auth_service.verify_otp(PHONE, "000000", PLATFORM)

    async def test_new_device_after_a_known_one_is_flagged_suspicious(
        self,
        auth_service: AuthService,
        mock_user_repo: AsyncMock,
        mock_session_repo: AsyncMock,
        mock_otp_service: AsyncMock,
    ) -> None:
        mock_otp_service.verify_otp.return_value = True
        mock_user_repo.get_by_phone.return_value = _build_user()
        mock_session_repo.list_active_sessions.return_value = [
            _build_session(device_info="Old Phone"),
        ]

        await auth_service.verify_otp(PHONE, "000000", PLATFORM, device_info="Brand New Phone")

        assert mock_session_repo.log_event.await_args.kwargs["is_suspicious"] is True

    async def test_first_ever_login_is_never_flagged_suspicious(
        self,
        auth_service: AuthService,
        mock_user_repo: AsyncMock,
        mock_session_repo: AsyncMock,
        mock_otp_service: AsyncMock,
    ) -> None:
        mock_otp_service.verify_otp.return_value = True
        mock_user_repo.get_by_phone.return_value = _build_user()
        mock_session_repo.list_active_sessions.return_value = []

        await auth_service.verify_otp(PHONE, "000000", PLATFORM, device_info="Brand New Phone")

        assert mock_session_repo.log_event.await_args.kwargs["is_suspicious"] is False

    async def test_same_known_device_is_not_suspicious(
        self,
        auth_service: AuthService,
        mock_user_repo: AsyncMock,
        mock_session_repo: AsyncMock,
        mock_otp_service: AsyncMock,
    ) -> None:
        mock_otp_service.verify_otp.return_value = True
        mock_user_repo.get_by_phone.return_value = _build_user()
        mock_session_repo.list_active_sessions.return_value = [_build_session(device_info="Pixel 7")]

        await auth_service.verify_otp(PHONE, "000000", PLATFORM, device_info="Pixel 7")

        assert mock_session_repo.log_event.await_args.kwargs["is_suspicious"] is False

    async def test_clears_failed_attempts_on_success_when_supported(
        self, mock_user_repo: AsyncMock, mock_session_repo: AsyncMock
    ) -> None:
        redis_otp = AsyncMock(spec=RedisOtpService)
        redis_otp.is_account_locked.return_value = False
        redis_otp.verify_otp.return_value = True
        mock_user_repo.get_by_phone.return_value = _build_user()
        service = AuthService(mock_user_repo, mock_session_repo, redis_otp)

        await service.verify_otp(PHONE, "000000", PLATFORM)

        redis_otp.clear_failed_attempts.assert_awaited_once_with(PHONE, PLATFORM)

    async def test_records_failed_attempt_on_wrong_otp_when_supported(
        self, mock_user_repo: AsyncMock, mock_session_repo: AsyncMock
    ) -> None:
        redis_otp = AsyncMock(spec=RedisOtpService)
        redis_otp.is_account_locked.return_value = False
        redis_otp.verify_otp.return_value = False
        mock_user_repo.get_by_phone.return_value = _build_user()
        service = AuthService(mock_user_repo, mock_session_repo, redis_otp)

        with pytest.raises(OtpError):
            await service.verify_otp(PHONE, "000000", PLATFORM)

        redis_otp.record_failed_attempt.assert_awaited_once_with(PHONE, PLATFORM)


class TestAdminLogin:
    ADMIN_EMAIL = "admin@divyangmatrimony.com"
    ADMIN_PASSWORD = "CorrectHorseBattery1"

    def _build_admin(self, **overrides: object) -> User:
        defaults: dict[str, object] = {
            "email": self.ADMIN_EMAIL,
            "phone": None,
            "role": AdminRoleEnum.ADMIN,
            "password_hash": hash_password(self.ADMIN_PASSWORD),
        }
        defaults.update(overrides)
        return _build_user(**defaults)

    async def test_correct_credentials_succeed(
        self,
        auth_service: AuthService,
        mock_user_repo: AsyncMock,
        mock_session_repo: AsyncMock,
    ) -> None:
        admin = self._build_admin()
        mock_user_repo.get_by_email.return_value = admin

        result = await auth_service.admin_login(self.ADMIN_EMAIL, self.ADMIN_PASSWORD, PLATFORM)

        assert result.is_new_user is False
        assert result.user.role == "ADMIN"
        mock_session_repo.create_session.assert_awaited_once()
        assert mock_session_repo.log_event.await_args.kwargs["event_type"] == LoginEventTypeEnum.LOGIN_SUCCESS

    async def test_unknown_email_is_rejected(
        self, auth_service: AuthService, mock_user_repo: AsyncMock, mock_session_repo: AsyncMock
    ) -> None:
        mock_user_repo.get_by_email.return_value = None

        with pytest.raises(UnauthorizedError):
            await auth_service.admin_login(self.ADMIN_EMAIL, self.ADMIN_PASSWORD, PLATFORM)

        mock_session_repo.log_event.assert_not_awaited()

    async def test_non_admin_user_with_matching_email_is_rejected(
        self, auth_service: AuthService, mock_user_repo: AsyncMock, mock_session_repo: AsyncMock
    ) -> None:
        mock_user_repo.get_by_email.return_value = self._build_admin(role=None)

        with pytest.raises(UnauthorizedError):
            await auth_service.admin_login(self.ADMIN_EMAIL, self.ADMIN_PASSWORD, PLATFORM)

        mock_session_repo.log_event.assert_not_awaited()

    async def test_wrong_password_is_rejected_and_logged(
        self, auth_service: AuthService, mock_user_repo: AsyncMock, mock_session_repo: AsyncMock
    ) -> None:
        admin = self._build_admin()
        mock_user_repo.get_by_email.return_value = admin

        with pytest.raises(UnauthorizedError):
            await auth_service.admin_login(self.ADMIN_EMAIL, "WrongPassword1", PLATFORM)

        assert mock_session_repo.log_event.await_args.kwargs["event_type"] == LoginEventTypeEnum.LOGIN_FAILED
        assert mock_session_repo.log_event.await_args.kwargs["user_id"] == admin.id

    async def test_banned_admin_is_rejected(
        self, auth_service: AuthService, mock_user_repo: AsyncMock
    ) -> None:
        mock_user_repo.get_by_email.return_value = self._build_admin(is_banned=True)

        with pytest.raises(AccountBannedError):
            await auth_service.admin_login(self.ADMIN_EMAIL, self.ADMIN_PASSWORD, PLATFORM)

    async def test_inactive_admin_is_rejected(
        self, auth_service: AuthService, mock_user_repo: AsyncMock
    ) -> None:
        mock_user_repo.get_by_email.return_value = self._build_admin(is_active=False)

        with pytest.raises(UnauthorizedError):
            await auth_service.admin_login(self.ADMIN_EMAIL, self.ADMIN_PASSWORD, PLATFORM)

    async def test_survives_a_needs_rehash_admin_password(
        self,
        auth_service: AuthService,
        mock_user_repo: AsyncMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Regression guard: whatever the (slightly odd) rehash branch does
        internally, `admin_login` must still complete and return tokens."""
        monkeypatch.setattr(auth_service_module, "password_needs_rehash", lambda _hash: True)
        mock_user_repo.get_by_email.return_value = self._build_admin()

        result = await auth_service.admin_login(self.ADMIN_EMAIL, self.ADMIN_PASSWORD, PLATFORM)

        assert result.tokens.access_token


class TestRefreshTokens:
    def _mint_refresh_token(
        self, user_id: uuid.UUID, *, expires_delta: timedelta | None = None
    ) -> tuple[str, uuid.UUID]:
        return create_refresh_token(user_id=user_id, platform_id=PLATFORM, expires_delta=expires_delta)

    async def test_rotates_a_valid_session(
        self,
        auth_service: AuthService,
        mock_user_repo: AsyncMock,
        mock_session_repo: AsyncMock,
    ) -> None:
        user = _build_user()
        token, jti = self._mint_refresh_token(user.id)
        old_session = _build_session(user_id=user.id, refresh_token_jti=str(jti))
        mock_session_repo.get_session_by_jti.return_value = old_session
        mock_user_repo.get_by_id.return_value = user

        new_tokens = await auth_service.refresh_tokens(token)

        assert new_tokens.access_token
        assert new_tokens.refresh_token
        mock_session_repo.revoke_session.assert_awaited_once_with(old_session)
        mock_session_repo.create_session.assert_awaited_once()
        assert (
            mock_session_repo.log_event.await_args.kwargs["event_type"]
            == LoginEventTypeEnum.TOKEN_REFRESH
        )

    async def test_carries_over_device_info_from_the_old_session(
        self,
        auth_service: AuthService,
        mock_user_repo: AsyncMock,
        mock_session_repo: AsyncMock,
    ) -> None:
        user = _build_user()
        token, jti = self._mint_refresh_token(user.id)
        old_session = _build_session(
            user_id=user.id, refresh_token_jti=str(jti), device_info="Pixel 7", ip_address="10.0.0.1"
        )
        mock_session_repo.get_session_by_jti.return_value = old_session
        mock_user_repo.get_by_id.return_value = user

        await auth_service.refresh_tokens(token)

        create_kwargs = mock_session_repo.create_session.await_args.kwargs
        assert create_kwargs["device_info"] == "Pixel 7"
        assert create_kwargs["ip_address"] == "10.0.0.1"

    async def test_expired_jwt_raises_token_expired(self, auth_service: AuthService) -> None:
        token, _jti = self._mint_refresh_token(uuid.uuid4(), expires_delta=timedelta(seconds=-1))

        with pytest.raises(TokenExpiredError):
            await auth_service.refresh_tokens(token)

    async def test_malformed_token_raises_invalid_token(self, auth_service: AuthService) -> None:
        with pytest.raises(InvalidTokenError):
            await auth_service.refresh_tokens("not-a-jwt-at-all")

    async def test_unknown_session_raises_invalid_token(
        self, auth_service: AuthService, mock_session_repo: AsyncMock
    ) -> None:
        token, _jti = self._mint_refresh_token(uuid.uuid4())
        mock_session_repo.get_session_by_jti.return_value = None

        with pytest.raises(InvalidTokenError):
            await auth_service.refresh_tokens(token)

    async def test_revoked_session_raises_invalid_token(
        self, auth_service: AuthService, mock_session_repo: AsyncMock
    ) -> None:
        token, jti = self._mint_refresh_token(uuid.uuid4())
        mock_session_repo.get_session_by_jti.return_value = _build_session(
            refresh_token_jti=str(jti), is_revoked=True
        )

        with pytest.raises(InvalidTokenError):
            await auth_service.refresh_tokens(token)

    async def test_expired_session_row_raises_token_expired(
        self, auth_service: AuthService, mock_session_repo: AsyncMock
    ) -> None:
        """The JWT itself hasn't expired, but the DB-tracked session has
        (Architecture §7.7 stateful revocation check)."""
        token, jti = self._mint_refresh_token(uuid.uuid4())
        mock_session_repo.get_session_by_jti.return_value = _build_session(
            refresh_token_jti=str(jti),
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )

        with pytest.raises(TokenExpiredError):
            await auth_service.refresh_tokens(token)

    async def test_missing_user_raises_unauthorized(
        self, auth_service: AuthService, mock_user_repo: AsyncMock, mock_session_repo: AsyncMock
    ) -> None:
        token, jti = self._mint_refresh_token(uuid.uuid4())
        mock_session_repo.get_session_by_jti.return_value = _build_session(refresh_token_jti=str(jti))
        mock_user_repo.get_by_id.return_value = None

        with pytest.raises(UnauthorizedError):
            await auth_service.refresh_tokens(token)

    async def test_banned_user_raises_unauthorized(
        self, auth_service: AuthService, mock_user_repo: AsyncMock, mock_session_repo: AsyncMock
    ) -> None:
        user = _build_user(is_banned=True)
        token, jti = self._mint_refresh_token(user.id)
        mock_session_repo.get_session_by_jti.return_value = _build_session(refresh_token_jti=str(jti))
        mock_user_repo.get_by_id.return_value = user

        with pytest.raises(UnauthorizedError):
            await auth_service.refresh_tokens(token)


class TestLogout:
    async def test_revokes_the_matching_session(
        self, auth_service: AuthService, mock_session_repo: AsyncMock
    ) -> None:
        token, jti = create_refresh_token(user_id=uuid.uuid4(), platform_id=PLATFORM)
        session = _build_session(refresh_token_jti=str(jti))
        mock_session_repo.get_session_by_jti.return_value = session

        await auth_service.logout(token, user_id=session.user_id)

        mock_session_repo.revoke_session.assert_awaited_once_with(session)
        assert mock_session_repo.log_event.await_args.kwargs["event_type"] == LoginEventTypeEnum.LOGOUT

    async def test_already_revoked_session_is_not_revoked_again(
        self, auth_service: AuthService, mock_session_repo: AsyncMock
    ) -> None:
        token, jti = create_refresh_token(user_id=uuid.uuid4(), platform_id=PLATFORM)
        mock_session_repo.get_session_by_jti.return_value = _build_session(
            refresh_token_jti=str(jti), is_revoked=True
        )

        await auth_service.logout(token, user_id=uuid.uuid4())

        mock_session_repo.revoke_session.assert_not_awaited()

    async def test_missing_session_still_logs_logout(
        self, auth_service: AuthService, mock_session_repo: AsyncMock
    ) -> None:
        token, _jti = create_refresh_token(user_id=uuid.uuid4(), platform_id=PLATFORM)
        mock_session_repo.get_session_by_jti.return_value = None

        await auth_service.logout(token, user_id=uuid.uuid4())

        mock_session_repo.revoke_session.assert_not_awaited()
        mock_session_repo.log_event.assert_awaited_once()

    async def test_expired_refresh_token_raises_invalid_token_not_token_expired(
        self, auth_service: AuthService
    ) -> None:
        """`logout` has a single `except jwt.InvalidTokenError` clause — an
        expired token surfaces as `InvalidTokenError`, unlike `refresh_tokens`
        which distinguishes `TokenExpiredError`."""
        token, _jti = create_refresh_token(
            user_id=uuid.uuid4(), platform_id=PLATFORM, expires_delta=timedelta(seconds=-1)
        )

        with pytest.raises(InvalidTokenError):
            await auth_service.logout(token, user_id=uuid.uuid4())

    async def test_malformed_token_raises_invalid_token(self, auth_service: AuthService) -> None:
        with pytest.raises(InvalidTokenError):
            await auth_service.logout("garbage", user_id=uuid.uuid4())


class TestLogoutAll:
    async def test_revokes_all_and_returns_the_count(
        self, auth_service: AuthService, mock_session_repo: AsyncMock
    ) -> None:
        mock_session_repo.revoke_all_sessions.return_value = 3
        user_id = uuid.uuid4()

        revoked = await auth_service.logout_all(user_id)

        assert revoked == 3
        mock_session_repo.revoke_all_sessions.assert_awaited_once_with(user_id)
        assert mock_session_repo.log_event.await_args.kwargs["event_type"] == LoginEventTypeEnum.LOGOUT


class TestListSessions:
    async def test_marks_the_matching_jti_as_current(
        self, auth_service: AuthService, mock_session_repo: AsyncMock
    ) -> None:
        current = _build_session(refresh_token_jti="current-jti")
        other = _build_session(refresh_token_jti="other-jti")
        mock_session_repo.list_active_sessions.return_value = [current, other]

        result = await auth_service.list_sessions(current.user_id, current_jti="current-jti")

        assert result.total == 2
        by_id = {s.id: s for s in result.sessions}
        assert by_id[current.id].is_current is True
        assert by_id[other.id].is_current is False

    async def test_no_current_jti_marks_nothing_current(
        self, auth_service: AuthService, mock_session_repo: AsyncMock
    ) -> None:
        session = _build_session()
        mock_session_repo.list_active_sessions.return_value = [session]

        result = await auth_service.list_sessions(session.user_id)

        assert result.sessions[0].is_current is False

    async def test_empty_list_yields_zero_total(
        self, auth_service: AuthService, mock_session_repo: AsyncMock
    ) -> None:
        mock_session_repo.list_active_sessions.return_value = []

        result = await auth_service.list_sessions(uuid.uuid4())

        assert result.total == 0
        assert result.sessions == []
