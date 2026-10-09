"""
OTP Service — abstract interface + concrete implementations.

Architecture does not specify an SMS vendor. The OTP service is an interface
so the concrete SMS provider can be swapped without touching the service layer.

Storage: OTPs are stored in Redis with TTL (not PostgreSQL).
Rationale: OTPs are short-lived (5 min), high-write, have no compliance
retention requirement. Redis TTL gives automatic expiry with no table bloat.

Redis key schema:
    otp:{platform_id}:{phone}           → JSON {code, attempts}
    otp_rate:{platform_id}:{phone}      → counter (TTL = 1 hour)
    auth_fail:{platform_id}:{phone}     → counter (TTL = lockout window)
    auth_lock:{platform_id}:{phone}     → sentinel (TTL = lockout duration)
"""
import json
import logging
import random
import string
from abc import ABC, abstractmethod

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

class IOtpService(ABC):
    """
    Abstract OTP service.

    Implement this interface for each SMS provider.
    The auth service depends only on this interface.
    """

    @abstractmethod
    async def send_otp(self, phone: str, platform_id: str) -> None:
        """
        Generate and send a fresh OTP to the given phone number.

        Raises OtpRateLimitError if the send rate limit is exceeded.
        """
        ...

    @abstractmethod
    async def verify_otp(self, phone: str, otp: str, platform_id: str) -> bool:
        """
        Verify the OTP for the given phone.

        Returns True if correct.
        Returns False if wrong (and increments attempt counter).
        Invalidates (deletes) the OTP after max_attempts wrong guesses.
        Does NOT raise — callers decide whether to raise OtpError.
        """
        ...

    @abstractmethod
    async def invalidate_otp(self, phone: str, platform_id: str) -> None:
        """Remove the OTP from storage (called after successful verification)."""
        ...


# ---------------------------------------------------------------------------
# Redis-backed implementation
# ---------------------------------------------------------------------------

class RedisOtpService(IOtpService):
    """
    Production OTP service backed by Redis.

    OTP codes are stored in Redis with TTL matching OTP_EXPIRE_SECONDS.
    A separate counter key enforces the per-phone send rate limit.
    """

    def __init__(self, redis: aioredis.Redis):
        self._redis = redis

    def _otp_key(self, phone: str, platform_id: str) -> str:
        return f"otp:{platform_id}:{phone}"

    def _rate_key(self, phone: str, platform_id: str) -> str:
        return f"otp_rate:{platform_id}:{phone}"

    def _fail_key(self, phone: str, platform_id: str) -> str:
        """Account-based failed-login counter key (Architecture §7.7)."""
        return f"auth_fail:{platform_id}:{phone}"

    def _lock_key(self, phone: str, platform_id: str) -> str:
        """Account lockout sentinel key."""
        return f"auth_lock:{platform_id}:{phone}"

    def _generate_code(self) -> str:
        return "".join(
            random.SystemRandom().choices(string.digits, k=settings.OTP_LENGTH)
        )

    async def is_account_locked(self, phone: str, platform_id: str) -> bool:
        """Check if the account is in a lockout period."""
        return await self._redis.exists(self._lock_key(phone, platform_id)) > 0

    async def record_failed_attempt(self, phone: str, platform_id: str) -> int:
        """
        Increment the failed-attempt counter.

        If the counter reaches AUTH_MAX_FAILED_ATTEMPTS, set the lockout key.
        Returns the current failure count after increment.
        """
        fail_key = self._fail_key(phone, platform_id)
        lock_key = self._lock_key(phone, platform_id)

        pipe = self._redis.pipeline()
        pipe.incr(fail_key)
        pipe.expire(fail_key, settings.AUTH_LOCKOUT_WINDOW_SECONDS)
        results = await pipe.execute()
        count: int = results[0]

        if count >= settings.AUTH_MAX_FAILED_ATTEMPTS:
            await self._redis.setex(
                lock_key,
                settings.AUTH_LOCKOUT_SECONDS,
                "locked",
            )
        return count

    async def clear_failed_attempts(self, phone: str, platform_id: str) -> None:
        """Clear failure counter after a successful login."""
        await self._redis.delete(
            self._fail_key(phone, platform_id),
            self._lock_key(phone, platform_id),
        )

    async def send_otp(self, phone: str, platform_id: str) -> None:
        """
        Generate, store, and send an OTP.

        Rate limit: OTP_RATE_LIMIT_PER_HOUR sends per phone per hour.
        """
        rate_key = self._rate_key(phone, platform_id)

        # Check send rate limit
        current_count = await self._redis.get(rate_key)
        if current_count and int(current_count) >= settings.OTP_RATE_LIMIT_PER_HOUR:
            from app.core.exceptions import OtpRateLimitError
            raise OtpRateLimitError()

        # Generate code and store with TTL
        code = self._generate_code()
        otp_key = self._otp_key(phone, platform_id)
        payload = json.dumps({"code": code, "attempts": 0})
        await self._redis.setex(otp_key, settings.OTP_EXPIRE_SECONDS, payload)

        # Increment rate counter (TTL = 1 hour)
        pipe = self._redis.pipeline()
        pipe.incr(rate_key)
        pipe.expire(rate_key, 3600)
        await pipe.execute()

        # Delegate to actual SMS provider (subclasses override _send_sms)
        await self._send_sms(phone, code)

    async def _send_sms(self, phone: str, code: str) -> None:
        """
        Deliver the OTP via SMS.

        Override in a concrete subclass (Twilio, MSG91, etc.).
        In this base implementation, logs to console for dev use.
        """
        logger.info(
            "OTP_SEND",
            extra={"phone": f"****{phone[-4:]}", "code": "REDACTED_IN_PROD"},
        )
        # In development, log the code. Production subclass sends real SMS.
        if settings.ENVIRONMENT == "development":
            print(f"\n[DEV OTP] Phone: {phone} | Code: {code}\n")

    async def verify_otp(self, phone: str, otp: str, platform_id: str) -> bool:
        """
        Verify submitted OTP against stored value.

        - Wrong code: increments attempt counter. Invalidates after max attempts.
        - Returns True on match.
        - Returns False on mismatch (caller raises OtpError if needed).
        """
        otp_key = self._otp_key(phone, platform_id)
        raw = await self._redis.get(otp_key)
        if not raw:
            return False

        data = json.loads(raw)
        attempts: int = data.get("attempts", 0)

        if data["code"] != otp:
            attempts += 1
            if attempts >= settings.OTP_MAX_ATTEMPTS:
                # Too many wrong guesses — invalidate
                await self._redis.delete(otp_key)
            else:
                data["attempts"] = attempts
                # Preserve remaining TTL
                ttl = await self._redis.ttl(otp_key)
                await self._redis.setex(otp_key, max(ttl, 1), json.dumps(data))
            return False

        return True

    async def invalidate_otp(self, phone: str, platform_id: str) -> None:
        """Delete OTP after successful verification."""
        await self._redis.delete(self._otp_key(phone, platform_id))


# ---------------------------------------------------------------------------
# Console implementation (dev/test — no Redis, no SMS)
# ---------------------------------------------------------------------------

class ConsoleOtpService(IOtpService):
    """
    Stub OTP service for local development and unit tests.

    Always generates code "000000" and prints it to stdout.
    No Redis required.
    """

    # In-memory store: {f"{platform_id}:{phone}": {"code": str, "attempts": int}}
    _store: dict[str, dict] = {}

    async def send_otp(self, phone: str, platform_id: str) -> None:
        key = f"{platform_id}:{phone}"
        code = "000000"
        self._store[key] = {"code": code, "attempts": 0}
        print(f"\n[CONSOLE OTP] Phone: {phone} | Code: {code}\n")

    async def verify_otp(self, phone: str, otp: str, platform_id: str) -> bool:
        key = f"{platform_id}:{phone}"
        entry = self._store.get(key)
        if not entry:
            return False
        if entry["code"] != otp:
            entry["attempts"] += 1
            if entry["attempts"] >= settings.OTP_MAX_ATTEMPTS:
                del self._store[key]
            return False
        return True

    async def invalidate_otp(self, phone: str, platform_id: str) -> None:
        key = f"{platform_id}:{phone}"
        self._store.pop(key, None)
