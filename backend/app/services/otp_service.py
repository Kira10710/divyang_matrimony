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
import hmac
import json
import logging
import random
import string
from abc import ABC, abstractmethod
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.exceptions import OtpRateLimitError, RateLimitError, ServiceUnavailableError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lua Scripts for Atomic Redis Operations
# ---------------------------------------------------------------------------

# 1. Atomic rate limit: checks global, IP, and phone counters, then increments with TTL
_CHECK_AND_INCR_RATE_LIMIT_LUA = """
local global_cnt = tonumber(redis.call('GET', KEYS[1]) or '0')
if global_cnt >= tonumber(ARGV[1]) then
    return 'ERR_GLOBAL_LIMIT'
end

if KEYS[2] ~= '' then
    local ip_cnt = tonumber(redis.call('GET', KEYS[2]) or '0')
    if ip_cnt >= tonumber(ARGV[3]) then
        return 'ERR_IP_LIMIT'
    end
end

local phone_cnt = tonumber(redis.call('GET', KEYS[3]) or '0')
if phone_cnt >= tonumber(ARGV[5]) then
    return 'ERR_PHONE_LIMIT'
end

local function incr_key(key, ttl)
    local n = redis.call('INCR', key)
    if n == 1 then
        redis.call('EXPIRE', key, ttl)
    end
    return n
end

incr_key(KEYS[1], tonumber(ARGV[2]))
if KEYS[2] ~= '' then
    incr_key(KEYS[2], tonumber(ARGV[4]))
end
incr_key(KEYS[3], tonumber(ARGV[6]))

return 'OK'
"""

# 2. Atomic rollback: if SMS dispatch fails, decrement counters and delete un-dispatched OTP
_ROLLBACK_RATE_LIMIT_LUA = """
local function decr_key(key)
    local n = redis.call('DECR', key)
    if n <= 0 then
        redis.call('DEL', key)
    end
    return n
end

if KEYS[1] ~= '' then decr_key(KEYS[1]) end
if KEYS[2] ~= '' then decr_key(KEYS[2]) end
if KEYS[3] ~= '' then decr_key(KEYS[3]) end
if KEYS[4] ~= '' then redis.call('DEL', KEYS[4]) end
return 'OK'
"""

# 3. Atomic verify: byte-by-byte constant-time comparison, atomic attempts counter increment,
#    auto-delete on max attempts
_VERIFY_OTP_LUA = """
local raw = redis.call('GET', KEYS[1])
if not raw then
    return 'NOT_FOUND'
end

local data = cjson.decode(raw)
local stored_code = tostring(data.code or '')
local input_code = tostring(ARGV[1] or '')

-- Constant-time comparison
local match = 0
if #stored_code == #input_code then
    local diff = 0
    for i = 1, #stored_code do
        local b1 = string.byte(stored_code, i)
        local b2 = string.byte(input_code, i)
        if b1 ~= b2 then
            diff = 1
        end
    end
    if diff == 0 then
        match = 1
    end
end

if match == 1 then
    return 'OK'
else
    local attempts = tonumber(data.attempts or 0) + 1
    if attempts >= tonumber(ARGV[2]) then
        redis.call('DEL', KEYS[1])
        return 'EXCEEDED'
    else
        data.attempts = attempts
        local ttl = redis.call('TTL', KEYS[1])
        if ttl > 0 then
            redis.call('SETEX', KEYS[1], ttl, cjson.encode(data))
        else
            redis.call('DEL', KEYS[1])
        end
        return 'MISMATCH'
    end
end
"""

# 4. Atomic admin IP rate limit
_ADMIN_IP_RATE_LIMIT_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
if current > tonumber(ARGV[2]) then
    return 'EXCEEDED'
end
return 'OK'
"""


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
    async def send_otp(
        self,
        phone: str,
        platform_id: str,
        *,
        ip_address: str | None = None,
    ) -> None:
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

    @abstractmethod
    async def check_admin_ip_rate_limit(self, ip_address: str, platform_id: str) -> None:
        """
        Enforce rate limits on admin login per IP.
        Raises RateLimitError if exceeded.
        """
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

    def _ip_rate_key(self, ip_address: str, platform_id: str) -> str:
        return f"otp_rate_ip:{platform_id}:{ip_address}"

    def _global_rate_key(self, platform_id: str) -> str:
        return f"otp_rate_global:{platform_id}"

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

    async def _safe_eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any:
        try:
            return await self._redis.eval(script, numkeys, *keys_and_args)
        except (aioredis.RedisError, ConnectionError, TimeoutError, OSError) as exc:
            logger.error("otp.redis_eval_failed: %s", exc)
            raise ServiceUnavailableError(
                "Authentication service is temporarily unavailable. Please try again shortly."
            ) from exc

    async def _safe_call(self, coro: Any) -> Any:
        try:
            return await coro
        except (aioredis.RedisError, ConnectionError, TimeoutError, OSError) as exc:
            logger.error("otp.redis_call_failed: %s", exc)
            raise ServiceUnavailableError(
                "Authentication service is temporarily unavailable. Please try again shortly."
            ) from exc

    async def _rollback_rate_limit(
        self,
        global_key: str,
        ip_key: str,
        rate_key: str,
        otp_key: str,
    ) -> None:
        """Rollback quota increments and delete un-dispatched OTP if delivery fails."""
        try:
            await self._redis.eval(
                _ROLLBACK_RATE_LIMIT_LUA,
                4,
                global_key,
                ip_key,
                rate_key,
                otp_key,
            )
        except Exception as exc:
            logger.warning("otp.rate_limit_rollback_failed: %s", exc)

    async def send_otp(
        self,
        phone: str,
        platform_id: str,
        *,
        ip_address: str | None = None,
    ) -> None:
        """
        Generate, store, and send an OTP.

        Enforces three layers of rate limits atomically via Lua script:
        1. Global rate limit (distributed abuse defense)
        2. Per-IP rate limit (IP abuse defense)
        3. Per-phone rate limit (phone spam defense)
        """
        global_key = self._global_rate_key(platform_id)
        ip_key = self._ip_rate_key(ip_address, platform_id) if ip_address else ""
        rate_key = self._rate_key(phone, platform_id)
        otp_key = self._otp_key(phone, platform_id)

        # 1. Atomic rate limit check and increment (fixed-window semantics)
        res = await self._safe_eval(
            _CHECK_AND_INCR_RATE_LIMIT_LUA,
            3,
            global_key,
            ip_key,
            rate_key,
            settings.OTP_GLOBAL_RATE_LIMIT_PER_MINUTE,
            60,
            settings.OTP_IP_RATE_LIMIT_PER_HOUR,
            3600,
            settings.OTP_RATE_LIMIT_PER_HOUR,
            3600,
        )

        if res == "ERR_GLOBAL_LIMIT":
            raise OtpRateLimitError("System OTP request limit reached. Please try again shortly.")
        elif res == "ERR_IP_LIMIT":
            raise OtpRateLimitError("Too many OTP requests from this network. Please try again later.")
        elif res == "ERR_PHONE_LIMIT":
            raise OtpRateLimitError()
        elif res != "OK":
            raise ServiceUnavailableError("Failed to enforce rate limit quotas.")

        # 2. Generate code and store with TTL
        code = self._generate_code()
        payload = json.dumps({"code": code, "attempts": 0})
        try:
            await self._safe_call(
                self._redis.setex(otp_key, settings.OTP_EXPIRE_SECONDS, payload)
            )
        except Exception:
            await self._rollback_rate_limit(global_key, ip_key, rate_key, otp_key)
            raise

        # 3. Delegate to actual SMS provider (subclasses override _send_sms)
        try:
            await self._send_sms(phone, code)
        except Exception:
            # If SMS delivery fails, rollback quota increments and clean up stale OTP
            await self._rollback_rate_limit(global_key, ip_key, rate_key, otp_key)
            raise

    async def _send_sms(self, phone: str, code: str) -> None:
        """
        Deliver the OTP via SMS.

        Override in a concrete subclass (Twilio, MSG91, etc.).
        In this base implementation, logs to console for dev use.
        Fails closed in non-development environments if no provider is configured.
        """
        logger.info(
            "OTP_SEND",
            extra={"phone": f"****{phone[-4:]}", "code": "REDACTED_IN_PROD"},
        )
        if settings.ENVIRONMENT == "development":
            print(f"\n[DEV OTP] Phone: {phone} | Code: {code}\n")
        else:
            raise ServiceUnavailableError(
                "SMS delivery provider is not configured for non-development environments"
            )

    async def verify_otp(self, phone: str, otp: str, platform_id: str) -> bool:
        """
        Verify submitted OTP against stored value atomically.

        - Constant-time comparison in Lua script.
        - Wrong code: increments attempt counter atomically.
        - Invalidates (deletes) OTP immediately upon reaching max attempts.
        - Returns True on match, False on mismatch/expired/invalid.
        """
        otp_key = self._otp_key(phone, platform_id)
        res = await self._safe_eval(
            _VERIFY_OTP_LUA,
            1,
            otp_key,
            otp,
            settings.OTP_MAX_ATTEMPTS,
        )
        return res == "OK"

    async def invalidate_otp(self, phone: str, platform_id: str) -> None:
        """Delete OTP after successful verification."""
        await self._safe_call(self._redis.delete(self._otp_key(phone, platform_id)))

    async def check_admin_ip_rate_limit(self, ip_address: str, platform_id: str) -> None:
        """Atomic per-IP rate limit for admin login."""
        key = f"admin_rate_ip:{platform_id}:{ip_address}"
        res = await self._safe_eval(
            _ADMIN_IP_RATE_LIMIT_LUA,
            1,
            key,
            settings.AUTH_LOCKOUT_SECONDS,
            settings.AUTH_ADMIN_IP_RATE_LIMIT,
        )
        if res == "EXCEEDED":
            raise RateLimitError("Too many admin login attempts from this network. Please try again later.")


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
    _store: dict[str, dict[str, Any]] = {}
    _ip_store: dict[str, int] = {}
    _admin_ip_store: dict[str, int] = {}

    def __init__(self) -> None:
        if settings.ENVIRONMENT != "development":
            raise RuntimeError("CRITICAL SECURITY ERROR: ConsoleOtpService cannot be used outside of development.")

    async def send_otp(
        self,
        phone: str,
        platform_id: str,
        *,
        ip_address: str | None = None,
    ) -> None:
        if ip_address:
            count = self._ip_store.get(ip_address, 0) + 1
            if count > settings.OTP_IP_RATE_LIMIT_PER_HOUR:
                raise OtpRateLimitError("Too many OTP requests from this network. Please try again later.")
            self._ip_store[ip_address] = count

        key = f"{platform_id}:{phone}"
        code = "000000"
        self._store[key] = {"code": code, "attempts": 0}
        print(f"\n[CONSOLE OTP] Phone: {phone} | Code: {code}\n")

    async def verify_otp(self, phone: str, otp: str, platform_id: str) -> bool:
        key = f"{platform_id}:{phone}"
        entry = self._store.get(key)
        if not entry:
            return False
        if not hmac.compare_digest(str(entry["code"]), str(otp)):
            entry["attempts"] += 1
            if entry["attempts"] >= settings.OTP_MAX_ATTEMPTS:
                del self._store[key]
            return False
        return True

    async def invalidate_otp(self, phone: str, platform_id: str) -> None:
        key = f"{platform_id}:{phone}"
        self._store.pop(key, None)

    async def check_admin_ip_rate_limit(self, ip_address: str, platform_id: str) -> None:
        count = self._admin_ip_store.get(ip_address, 0) + 1
        if count > settings.AUTH_ADMIN_IP_RATE_LIMIT:
            raise RateLimitError("Too many admin login attempts from this network. Please try again later.")
        self._admin_ip_store[ip_address] = count
