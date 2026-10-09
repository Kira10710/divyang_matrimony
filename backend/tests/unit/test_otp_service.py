"""
OTP tests for `app.services.otp_service`.

Covers the production `RedisOtpService` (backed by `FakeRedis` — no real
Redis needed, see `tests/fakes.py`) and the dev/test `ConsoleOtpService`.
"""
from __future__ import annotations

import json

import pytest

from app.core.config import settings
from app.core.exceptions import OtpRateLimitError
from app.services.otp_service import ConsoleOtpService, RedisOtpService

from ..fakes import FakeRedis

PHONE = "+919876543210"
OTHER_PHONE = "+919876500000"
PLATFORM = "divyang_matrimony"


def _flip(code: str) -> str:
    """A digit string guaranteed to differ from `code`."""
    first = "1" if code[0] != "1" else "2"
    return first + code[1:]


@pytest.fixture
def otp_service(fake_redis: FakeRedis) -> RedisOtpService:
    return RedisOtpService(fake_redis)


class TestRedisOtpServiceSendOtp:
    async def test_stores_a_code_with_the_configured_length(
        self, otp_service: RedisOtpService, fake_redis: FakeRedis
    ) -> None:
        await otp_service.send_otp(PHONE, PLATFORM)

        raw = await fake_redis.get(f"otp:{PLATFORM}:{PHONE}")
        assert raw is not None
        payload = json.loads(raw)
        assert len(payload["code"]) == settings.OTP_LENGTH
        assert payload["code"].isdigit()
        assert payload["attempts"] == 0

    async def test_sets_a_ttl_matching_otp_expiry(
        self, otp_service: RedisOtpService, fake_redis: FakeRedis
    ) -> None:
        await otp_service.send_otp(PHONE, PLATFORM)

        ttl = await fake_redis.ttl(f"otp:{PLATFORM}:{PHONE}")
        assert 0 < ttl <= settings.OTP_EXPIRE_SECONDS

    async def test_enforces_the_per_phone_rate_limit(
        self, otp_service: RedisOtpService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "OTP_RATE_LIMIT_PER_HOUR", 2)

        await otp_service.send_otp(PHONE, PLATFORM)
        await otp_service.send_otp(PHONE, PLATFORM)

        with pytest.raises(OtpRateLimitError):
            await otp_service.send_otp(PHONE, PLATFORM)

    async def test_rate_limit_is_scoped_per_phone(
        self, otp_service: RedisOtpService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "OTP_RATE_LIMIT_PER_HOUR", 1)

        await otp_service.send_otp(PHONE, PLATFORM)

        # A different phone number has its own independent counter.
        await otp_service.send_otp(OTHER_PHONE, PLATFORM)

    async def test_resending_overwrites_the_previous_code(
        self, otp_service: RedisOtpService, fake_redis: FakeRedis
    ) -> None:
        await otp_service.send_otp(PHONE, PLATFORM)
        first_code = json.loads(await fake_redis.get(f"otp:{PLATFORM}:{PHONE}"))["code"]

        await otp_service.send_otp(PHONE, PLATFORM)

        assert await otp_service.verify_otp(PHONE, first_code, PLATFORM) is False


class TestRedisOtpServiceVerifyOtp:
    async def test_correct_code_verifies(
        self, otp_service: RedisOtpService, fake_redis: FakeRedis
    ) -> None:
        await otp_service.send_otp(PHONE, PLATFORM)
        code = json.loads(await fake_redis.get(f"otp:{PLATFORM}:{PHONE}"))["code"]

        assert await otp_service.verify_otp(PHONE, code, PLATFORM) is True

    async def test_wrong_code_fails_and_increments_attempts(
        self, otp_service: RedisOtpService, fake_redis: FakeRedis
    ) -> None:
        await otp_service.send_otp(PHONE, PLATFORM)
        code = json.loads(await fake_redis.get(f"otp:{PLATFORM}:{PHONE}"))["code"]

        assert await otp_service.verify_otp(PHONE, _flip(code), PLATFORM) is False

        payload = json.loads(await fake_redis.get(f"otp:{PLATFORM}:{PHONE}"))
        assert payload["attempts"] == 1

    async def test_correct_code_still_works_after_the_wrong_code(
        self, otp_service: RedisOtpService, fake_redis: FakeRedis
    ) -> None:
        """Below the max-attempts threshold, the OTP survives a wrong guess."""
        await otp_service.send_otp(PHONE, PLATFORM)
        code = json.loads(await fake_redis.get(f"otp:{PLATFORM}:{PHONE}"))["code"]

        await otp_service.verify_otp(PHONE, _flip(code), PLATFORM)

        assert await otp_service.verify_otp(PHONE, code, PLATFORM) is True

    async def test_max_attempts_invalidates_the_otp(
        self, otp_service: RedisOtpService, fake_redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "OTP_MAX_ATTEMPTS", 2)
        await otp_service.send_otp(PHONE, PLATFORM)
        code = json.loads(await fake_redis.get(f"otp:{PLATFORM}:{PHONE}"))["code"]
        wrong = _flip(code)

        assert await otp_service.verify_otp(PHONE, wrong, PLATFORM) is False
        assert await otp_service.verify_otp(PHONE, wrong, PLATFORM) is False

        assert await fake_redis.get(f"otp:{PLATFORM}:{PHONE}") is None
        # Even the correct code no longer works — the OTP was deleted.
        assert await otp_service.verify_otp(PHONE, code, PLATFORM) is False

    async def test_verify_without_a_prior_send_returns_false(
        self, otp_service: RedisOtpService
    ) -> None:
        assert await otp_service.verify_otp(PHONE, "123456", PLATFORM) is False

    async def test_invalidate_removes_the_otp(
        self, otp_service: RedisOtpService, fake_redis: FakeRedis
    ) -> None:
        await otp_service.send_otp(PHONE, PLATFORM)

        await otp_service.invalidate_otp(PHONE, PLATFORM)

        assert await fake_redis.get(f"otp:{PLATFORM}:{PHONE}") is None


class TestRedisOtpServiceAccountLockout:
    """Architecture §7.7 — account-based lockout, independent of the
    OTP-specific rate limit above."""

    async def test_not_locked_initially(self, otp_service: RedisOtpService) -> None:
        assert await otp_service.is_account_locked(PHONE, PLATFORM) is False

    async def test_locks_after_max_failed_attempts(
        self, otp_service: RedisOtpService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "AUTH_MAX_FAILED_ATTEMPTS", 3)

        for _ in range(2):
            await otp_service.record_failed_attempt(PHONE, PLATFORM)
        assert await otp_service.is_account_locked(PHONE, PLATFORM) is False

        await otp_service.record_failed_attempt(PHONE, PLATFORM)

        assert await otp_service.is_account_locked(PHONE, PLATFORM) is True

    async def test_record_failed_attempt_returns_running_count(
        self, otp_service: RedisOtpService
    ) -> None:
        assert await otp_service.record_failed_attempt(PHONE, PLATFORM) == 1
        assert await otp_service.record_failed_attempt(PHONE, PLATFORM) == 2

    async def test_clear_failed_attempts_unlocks_the_account(
        self, otp_service: RedisOtpService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "AUTH_MAX_FAILED_ATTEMPTS", 1)
        await otp_service.record_failed_attempt(PHONE, PLATFORM)
        assert await otp_service.is_account_locked(PHONE, PLATFORM) is True

        await otp_service.clear_failed_attempts(PHONE, PLATFORM)

        assert await otp_service.is_account_locked(PHONE, PLATFORM) is False

    async def test_lockout_is_scoped_per_phone(
        self, otp_service: RedisOtpService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "AUTH_MAX_FAILED_ATTEMPTS", 1)

        await otp_service.record_failed_attempt(PHONE, PLATFORM)

        assert await otp_service.is_account_locked(OTHER_PHONE, PLATFORM) is False


class TestConsoleOtpService:
    """Dev/test stub — always uses the fixed code "000000" (no Redis)."""

    @pytest.fixture(autouse=True)
    def _isolate_class_state(self) -> None:
        # `ConsoleOtpService._store` is a class-level dict shared across
        # every instance (see app/services/otp_service.py) — clear it
        # around each test so tests never leak OTP state into each other.
        ConsoleOtpService._store.clear()
        yield
        ConsoleOtpService._store.clear()

    async def test_send_otp_always_uses_the_fixed_dev_code(self) -> None:
        service = ConsoleOtpService()
        await service.send_otp(PHONE, PLATFORM)

        assert await service.verify_otp(PHONE, "000000", PLATFORM) is True

    async def test_wrong_code_fails(self) -> None:
        service = ConsoleOtpService()
        await service.send_otp(PHONE, PLATFORM)

        assert await service.verify_otp(PHONE, "111111", PLATFORM) is False

    async def test_max_attempts_invalidates_the_otp(self) -> None:
        service = ConsoleOtpService()
        await service.send_otp(PHONE, PLATFORM)

        for _ in range(settings.OTP_MAX_ATTEMPTS):
            await service.verify_otp(PHONE, "111111", PLATFORM)

        assert await service.verify_otp(PHONE, "000000", PLATFORM) is False

    async def test_invalidate_removes_the_entry(self) -> None:
        service = ConsoleOtpService()
        await service.send_otp(PHONE, PLATFORM)

        await service.invalidate_otp(PHONE, PLATFORM)

        assert await service.verify_otp(PHONE, "000000", PLATFORM) is False

    async def test_verify_without_a_prior_send_returns_false(self) -> None:
        service = ConsoleOtpService()

        assert await service.verify_otp(PHONE, "000000", PLATFORM) is False
