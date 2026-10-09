"""
End-to-end auth journeys — several endpoints chained together over real
HTTP requests, the way an actual client would use them.

`tests/integration/test_auth_api.py` covers each endpoint in isolation;
this file is about the *sequences* — session rotation, multi-device
logout, and the registration-to-authenticated-request round trip.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from ..fakes import FakeRedis
from ..support import auth_headers, decode_jti, login


class TestRegistrationToAuthenticatedRequest:
    def test_a_brand_new_phone_can_immediately_call_a_protected_endpoint(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        data = login(app_client, fake_redis, device_info="Pixel 7")
        assert data["is_new_user"] is True

        me_response = app_client.get(
            "/api/v1/auth/me", headers=auth_headers(data["tokens"]["access_token"])
        )

        assert me_response.status_code == 200
        assert me_response.json()["data"]["id"] == data["user"]["id"]

    def test_the_same_phone_logging_in_again_is_a_returning_user(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        first = login(app_client, fake_redis)
        second = login(app_client, fake_redis)

        assert first["is_new_user"] is True
        assert second["is_new_user"] is False
        assert first["user"]["id"] == second["user"]["id"]


class TestRefreshRotationChain:
    def test_each_refresh_invalidates_the_one_before_it(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        data = login(app_client, fake_redis)
        refresh_token_0 = data["tokens"]["refresh_token"]

        first_refresh = app_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token_0}
        )
        assert first_refresh.status_code == 200
        refresh_token_1 = first_refresh.json()["data"]["refresh_token"]

        second_refresh = app_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token_1}
        )
        assert second_refresh.status_code == 200
        refresh_token_2 = second_refresh.json()["data"]["refresh_token"]

        # Every token before the most recent one is now dead.
        for stale_token in (refresh_token_0, refresh_token_1):
            replay = app_client.post("/api/v1/auth/refresh", json={"refresh_token": stale_token})
            assert replay.status_code == 401

        # Only the latest one still works.
        final = app_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token_2})
        assert final.status_code == 200

    def test_a_refreshed_access_token_still_authenticates(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        data = login(app_client, fake_redis)

        refreshed = app_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": data["tokens"]["refresh_token"]}
        ).json()["data"]

        me_response = app_client.get(
            "/api/v1/auth/me", headers=auth_headers(refreshed["access_token"])
        )
        assert me_response.status_code == 200


class TestMultiDeviceSessions:
    def test_logging_in_from_two_devices_creates_two_sessions(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        phone_a = login(app_client, fake_redis, device_info="Device A")
        login(app_client, fake_redis, device_info="Device B")

        sessions = app_client.get(
            "/api/v1/auth/sessions", headers=auth_headers(phone_a["tokens"]["access_token"])
        ).json()["data"]

        assert sessions["total"] == 2
        device_names = {s["device_info"] for s in sessions["sessions"]}
        assert device_names == {"Device A", "Device B"}

    def test_logging_out_one_device_leaves_the_other_active(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        device_a = login(app_client, fake_redis, device_info="Device A")
        device_b = login(app_client, fake_redis, device_info="Device B")

        logout_response = app_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": device_a["tokens"]["refresh_token"]},
            headers=auth_headers(device_a["tokens"]["access_token"]),
        )
        assert logout_response.status_code == 200

        sessions = app_client.get(
            "/api/v1/auth/sessions", headers=auth_headers(device_b["tokens"]["access_token"])
        ).json()["data"]
        assert sessions["total"] == 1
        assert sessions["sessions"][0]["device_info"] == "Device B"

        # Device A's refresh token is dead; device B's is untouched.
        assert (
            app_client.post(
                "/api/v1/auth/refresh", json={"refresh_token": device_a["tokens"]["refresh_token"]}
            ).status_code
            == 401
        )
        assert (
            app_client.post(
                "/api/v1/auth/refresh", json={"refresh_token": device_b["tokens"]["refresh_token"]}
            ).status_code
            == 200
        )

    def test_logout_all_ends_every_device_at_once(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        device_a = login(app_client, fake_redis, device_info="Device A")
        device_b = login(app_client, fake_redis, device_info="Device B")

        response = app_client.post(
            "/api/v1/auth/logout-all", headers=auth_headers(device_a["tokens"]["access_token"])
        )

        assert response.json()["data"]["revoked_sessions"] == 2
        for device in (device_a, device_b):
            refresh_result = app_client.post(
                "/api/v1/auth/refresh", json={"refresh_token": device["tokens"]["refresh_token"]}
            )
            assert refresh_result.status_code == 401

    def test_current_session_is_correctly_identified_among_several(
        self, app_client: TestClient, fake_redis: FakeRedis
    ) -> None:
        login(app_client, fake_redis, device_info="Device A")
        device_b = login(app_client, fake_redis, device_info="Device B")
        jti_b = decode_jti(device_b["tokens"]["refresh_token"])

        sessions = app_client.get(
            "/api/v1/auth/sessions",
            headers={**auth_headers(device_b["tokens"]["access_token"]), "X-Session-JTI": jti_b},
        ).json()["data"]["sessions"]

        current = {s["device_info"]: s["is_current"] for s in sessions}
        assert current == {"Device A": False, "Device B": True}
