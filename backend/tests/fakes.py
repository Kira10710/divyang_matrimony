"""
In-memory test doubles for external I/O the auth module depends on.

Only [FakeRedis] lives here. It implements the exact subset of the
`redis.asyncio.Redis` API that `app.services.otp_service.RedisOtpService`
calls (`get`, `setex`, `delete`, `exists`, `ttl`, `pipeline()`), so tests can
exercise the *real* `RedisOtpService` business logic (rate limiting, wrong-
attempt counting, account lockout) without a running Redis server.

Deliberately not a general-purpose Redis mock — extend it only if
`RedisOtpService` starts calling something new.
"""
from __future__ import annotations

import time


class _FakePipeline:
    """Mimics `redis.asyncio.Redis.pipeline()` — queues commands, runs them
    in order on `execute()`, and returns their results as a list (matching
    real redis-py pipeline semantics closely enough for `RedisOtpService`,
    which only ever calls `.incr()` + `.expire()` through a pipeline).
    """

    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis
        self._ops: list[tuple[str, tuple[object, ...]]] = []

    def incr(self, key: str) -> _FakePipeline:
        self._ops.append(("incr", (key,)))
        return self

    def expire(self, key: str, seconds: int) -> _FakePipeline:
        self._ops.append(("expire", (key, seconds)))
        return self

    async def execute(self) -> list[object]:
        results: list[object] = []
        for name, args in self._ops:
            method = getattr(self._redis, name)
            results.append(await method(*args))
        self._ops.clear()
        return results


class FakeRedis:
    """In-memory stand-in for an async redis-py client.

    Values are always stored/returned as `str`, matching the production
    client's `decode_responses=True` configuration (see `app/core/redis.py`).
    """

    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._expires_at: dict[str, float] = {}

    def _is_expired(self, key: str) -> bool:
        expires_at = self._expires_at.get(key)
        return expires_at is not None and expires_at <= time.monotonic()

    def _purge_if_expired(self, key: str) -> None:
        if self._is_expired(key):
            self._values.pop(key, None)
            self._expires_at.pop(key, None)

    async def get(self, key: str) -> str | None:
        self._purge_if_expired(key)
        return self._values.get(key)

    async def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        self._values[key] = value
        self._expires_at[key] = time.monotonic() + ttl_seconds

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._values:
                del self._values[key]
                self._expires_at.pop(key, None)
                deleted += 1
        return deleted

    async def exists(self, key: str) -> int:
        self._purge_if_expired(key)
        return 1 if key in self._values else 0

    async def ttl(self, key: str) -> int:
        self._purge_if_expired(key)
        if key not in self._values:
            return -2  # redis convention: key does not exist
        expires_at = self._expires_at.get(key)
        if expires_at is None:
            return -1  # redis convention: key exists, no TTL
        return max(0, int(expires_at - time.monotonic()))

    async def incr(self, key: str) -> int:
        self._purge_if_expired(key)
        current = int(self._values.get(key, "0"))
        current += 1
        self._values[key] = str(current)
        return current

    async def expire(self, key: str, seconds: int) -> bool:
        if key not in self._values:
            return False
        self._expires_at[key] = time.monotonic() + seconds
        return True

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self)

    # --- Test-only inspection helpers (not part of the real Redis API) ---

    def set_ttl_remaining(self, key: str, seconds: int) -> None:
        """Force a key's remaining TTL — used to test near-expiry edge cases
        without sleeping in real time."""
        self._expires_at[key] = time.monotonic() + seconds

    def expire_now(self, key: str) -> None:
        """Simulate immediate expiry of a key, as if its TTL had elapsed."""
        self._values.pop(key, None)
        self._expires_at.pop(key, None)
