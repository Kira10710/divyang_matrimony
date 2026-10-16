"""
OTP tests for `app.services.otp_service`.

Covers the production `RedisOtpService` (backed by `FakeRedis` — no real
Redis needed, see `tests/fakes.py`) and the dev/test `ConsoleOtpService`.
"""
from __future__ import annotations

import json

import pytest

from app.core.config import settings
from app.core.exceptions import OtpRateLimitError, ServiceUnavailableError
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

    async def test_enforces_the_per_ip_rate_limit(
        self, otp_service: RedisOtpService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "OTP_IP_RATE_LIMIT_PER_HOUR", 2)
        ip = "192.168.1.100"

        await otp_service.send_otp(PHONE, PLATFORM, ip_address=ip)
        await otp_service.send_otp(OTHER_PHONE, PLATFORM, ip_address=ip)

        with pytest.raises(OtpRateLimitError, match="Too many OTP requests from this network"):
            await otp_service.send_otp("+919999999999", PLATFORM, ip_address=ip)

    async def test_enforces_the_global_rate_limit(
        self, otp_service: RedisOtpService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "OTP_GLOBAL_RATE_LIMIT_PER_MINUTE", 2)

        await otp_service.send_otp(PHONE, PLATFORM)
        await otp_service.send_otp(OTHER_PHONE, PLATFORM)

        with pytest.raises(OtpRateLimitError, match="System OTP request limit reached"):
            await otp_service.send_otp("+919999999999", PLATFORM)

    async def test_non_development_environment_fails_closed_without_sms_provider(
        self, otp_service: RedisOtpService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")

        with pytest.raises(ServiceUnavailableError, match="SMS delivery provider is not configured"):
            await otp_service.send_otp(PHONE, PLATFORM)

    async def test_concurrent_otp_sends_respect_configured_quota(
        self, otp_service: RedisOtpService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asyncio
        monkeypatch.setattr(settings, "OTP_RATE_LIMIT_PER_HOUR", 3)

        results = await asyncio.gather(
            *[otp_service.send_otp(PHONE, PLATFORM) for _ in range(6)],
            return_exceptions=True,
        )

        successes = [r for r in results if not isinstance(r, Exception)]
        rate_limits = [r for r in results if isinstance(r, OtpRateLimitError)]

        assert len(successes) == 3
        assert len(rate_limits) == 3

    async def test_rate_limit_counter_sets_ttl_only_on_first_increment(
        self, otp_service: RedisOtpService, fake_redis: FakeRedis
    ) -> None:
        import time
        await otp_service.send_otp(PHONE, PLATFORM)
        ttl1 = await fake_redis.ttl(f"otp_rate:{PLATFORM}:{PHONE}")
        assert 3590 <= ttl1 <= 3600

        # Advance expiration simulating elapsed time
        key = f"otp_rate:{PLATFORM}:{PHONE}"
        fake_redis._expires_at[key] = time.monotonic() + 1800

        # Subsequent increment in same window must preserve existing TTL
        await otp_service.send_otp(PHONE, PLATFORM)
        ttl2 = await fake_redis.ttl(key)
        assert 1790 <= ttl2 <= 1800

    async def test_redis_failure_raises_service_unavailable(
        self, otp_service: RedisOtpService, fake_redis: FakeRedis
    ) -> None:
        from unittest.mock import AsyncMock

        import redis.asyncio as aioredis
        fake_redis.eval = AsyncMock(side_effect=aioredis.RedisError("Connection refused"))

        with pytest.raises(ServiceUnavailableError, match="Authentication service is temporarily unavailable"):
            await otp_service.send_otp(PHONE, PLATFORM)

    async def test_failed_sms_dispatch_rolls_back_rate_limit_and_cleans_stale_otp(
        self, otp_service: RedisOtpService, fake_redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import AsyncMock
        monkeypatch.setattr(settings, "OTP_RATE_LIMIT_PER_HOUR", 1)

        otp_service._send_sms = AsyncMock(side_effect=RuntimeError("SMS provider down"))

        with pytest.raises(RuntimeError, match="SMS provider down"):
            await otp_service.send_otp(PHONE, PLATFORM)

        # Quota rolled back
        rate_val = await fake_redis.get(f"otp_rate:{PLATFORM}:{PHONE}")
        assert rate_val is None or int(rate_val) == 0

        # Un-dispatched OTP deleted
        assert await fake_redis.get(f"otp:{PLATFORM}:{PHONE}") is None

        # Next send is permitted
        otp_service._send_sms = AsyncMock(return_value=None)
        await otp_service.send_otp(PHONE, PLATFORM)
        assert await fake_redis.get(f"otp:{PLATFORM}:{PHONE}") is not None


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

    async def test_concurrent_otp_verification_failures_atomic_lockout(
        self, otp_service: RedisOtpService, fake_redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import asyncio
        monkeypatch.setattr(settings, "OTP_MAX_ATTEMPTS", 3)
        await otp_service.send_otp(PHONE, PLATFORM)
        code = json.loads(await fake_redis.get(f"otp:{PLATFORM}:{PHONE}"))["code"]
        wrong = _flip(code)

        results = await asyncio.gather(
            *[otp_service.verify_otp(PHONE, wrong, PLATFORM) for _ in range(5)]
        )

        assert all(r is False for r in results)
        assert await fake_redis.get(f"otp:{PLATFORM}:{PHONE}") is None
        assert await otp_service.verify_otp(PHONE, code, PLATFORM) is False

    async def test_verify_otp_redis_failure_raises_service_unavailable(
        self, otp_service: RedisOtpService, fake_redis: FakeRedis
    ) -> None:
        from unittest.mock import AsyncMock

        import redis.asyncio as aioredis
        fake_redis.eval = AsyncMock(side_effect=aioredis.RedisError("Connection reset"))

        with pytest.raises(ServiceUnavailableError, match="Authentication service is temporarily unavailable"):
            await otp_service.verify_otp(PHONE, "123456", PLATFORM)

    async def test_admin_ip_rate_limit_enforced_and_tracks_fixed_window(
        self, otp_service: RedisOtpService, fake_redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.core.exceptions import RateLimitError
        monkeypatch.setattr(settings, "AUTH_ADMIN_IP_RATE_LIMIT", 2)
        ip = "192.0.2.1"

        await otp_service.check_admin_ip_rate_limit(ip, PLATFORM)
        await otp_service.check_admin_ip_rate_limit(ip, PLATFORM)

        with pytest.raises(RateLimitError, match="Too many admin login attempts"):
            await otp_service.check_admin_ip_rate_limit(ip, PLATFORM)


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
