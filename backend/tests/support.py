"""
Shared helpers for HTTP-level auth tests (`tests/integration/`).

Not a fixture module — plain functions, imported directly by test modules
that need to log a user in over HTTP or peek at an OTP the API sent.
"""
from __future__ import annotations

import asyncio
import json

import jwt as pyjwt
from fastapi.testclient import TestClient

from .fakes import FakeRedis

PLATFORM = "divyang_matrimony"
PHONE = "+919876543210"


def get_otp_code(fake_redis: FakeRedis, phone: str, platform: str = PLATFORM) -> str:
    """Reads the OTP `RedisOtpService` just generated for `phone` straight
    out of the fake Redis store — the code is random, so tests can't
    predict it, only observe it after the fact."""
    raw = asyncio.run(fake_redis.get(f"otp:{platform}:{phone}"))
    assert raw is not None, "no OTP was ever sent for this phone"
    payload: dict[str, object] = json.loads(raw)
    return str(payload["code"])


def wrong_code(code: str) -> str:
    """A digit string guaranteed to differ from `code`."""
    first = "1" if code[0] != "1" else "2"
    return first + code[1:]


def decode_jti(token: str) -> str:
    """Reads the `jti` claim out of a refresh token without verifying its
    signature — tests use this to set `X-Session-JTI`, same as a real
    client would after receiving the token."""
    payload: dict[str, object] = pyjwt.decode(token, options={"verify_signature": False})
    return str(payload["jti"])


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def login(client: TestClient, fake_redis: FakeRedis, phone: str = PHONE, **extra: object) -> dict:
    """Full send-otp -> verify-otp round trip over HTTP. Returns the `data`
    payload of the verify-otp response (`user`, `tokens`, `is_new_user`)."""
    client.post("/api/v1/auth/send-otp", json={"phone": phone})
    code = get_otp_code(fake_redis, phone)
    response = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": code, **extra})
    assert response.status_code == 200, response.text
    return response.json()["data"]
