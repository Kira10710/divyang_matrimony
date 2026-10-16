"""Route-level regression tests for profile and photo authorization."""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.core.dependencies import get_photo_service, get_profile_service
from app.core.exceptions import NotFoundError
from app.core.security import create_access_token
from app.models.enums import VisibilityTier
from app.models.user import AdminRoleEnum
from app.schemas.photo import PhotoListOut


def _headers_for(user) -> dict[str, str]:
    token = create_access_token(user.id, user.platform_id)
    return {"Authorization": f"Bearer {token}"}


def _create_profile(app_client, user) -> str:
    response = app_client.post(
        "/api/v1/profiles",
        headers=_headers_for(user),
        json={
            "first_name": "Priya",
            "last_name": "Patel",
            "gender": "FEMALE",
            "date_of_birth": "1998-03-20",
            "marital_status": "NEVER_MARRIED",
            "disability_type": "PHYSICAL",
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()["data"]["id"]


def _set_profile_visibility(app_client, user, visible: bool) -> None:
    response = app_client.patch(
        "/api/v1/profiles/me",
        headers=_headers_for(user),
        json={"is_profile_visible": visible},
    )
    assert response.status_code == 200, response.json()


def _override_photo_service(app_client) -> AsyncMock:
    photo_service = AsyncMock()
    photo_service.list_photos.return_value = PhotoListOut(photos=[], total=0)
    app_client.app.dependency_overrides[get_photo_service] = lambda: photo_service
    return photo_service


def test_sensitive_me_route_is_not_captured_by_profile_id_route(app_client, make_user) -> None:
    user = asyncio.run(make_user())

    response = app_client.get("/api/v1/profiles/me/sensitive", headers=_headers_for(user))

    # The user has no profile, so the literal handler returns its normal 404.
    # Before the UUID path converter, the dynamic route captured "me" and
    # returned a 422 UUID validation error instead.
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "NOT_FOUND"


def test_photo_list_uses_profile_authorization_tier(app_client, make_user) -> None:
    user = asyncio.run(make_user())
    target_profile_id = uuid.uuid4()
    profile_service = AsyncMock()
    profile_service.get_profile_by_id.return_value = SimpleNamespace(visibility_tier=VisibilityTier.REGISTERED)
    photo_service = AsyncMock()
    photo_service.list_photos.return_value = PhotoListOut(photos=[], total=0)
    app_client.app.dependency_overrides[get_profile_service] = lambda: profile_service
    app_client.app.dependency_overrides[get_photo_service] = lambda: photo_service

    try:
        response = app_client.get(
            f"/api/v1/profiles/{target_profile_id}/photos",
            headers=_headers_for(user),
        )
    finally:
        app_client.app.dependency_overrides.pop(get_profile_service, None)
        app_client.app.dependency_overrides.pop(get_photo_service, None)

    assert response.status_code == 200
    profile_service.get_profile_by_id.assert_awaited_once()
    call = profile_service.get_profile_by_id.await_args
    assert call.args[0] == target_profile_id
    assert call.args[1].id == user.id
    assert call.kwargs == {
        "has_active_subscription": False,
        "has_mutual_interest": False,
    }
    assert photo_service.list_photos.await_args.kwargs["viewer_tier"] == VisibilityTier.REGISTERED


def test_photo_list_stops_before_signing_urls_when_profile_is_hidden(app_client, make_user) -> None:
    user = asyncio.run(make_user())
    target_profile_id = uuid.uuid4()
    profile_service = AsyncMock()
    profile_service.get_profile_by_id.side_effect = NotFoundError("Profile not found")
    photo_service = AsyncMock()
    app_client.app.dependency_overrides[get_profile_service] = lambda: profile_service
    app_client.app.dependency_overrides[get_photo_service] = lambda: photo_service

    try:
        response = app_client.get(
            f"/api/v1/profiles/{target_profile_id}/photos",
            headers=_headers_for(user),
        )
    finally:
        app_client.app.dependency_overrides.pop(get_profile_service, None)
        app_client.app.dependency_overrides.pop(get_photo_service, None)

    assert response.status_code == 404
    photo_service.list_photos.assert_not_awaited()


def test_hidden_profile_http_access_is_limited_to_owner_and_admin(app_client, make_user, make_admin) -> None:
    owner = asyncio.run(make_user())
    unrelated_user = asyncio.run(make_user())
    support_user = asyncio.run(make_admin(role=AdminRoleEnum.SUPPORT))
    admin_user = asyncio.run(make_admin())
    profile_id = _create_profile(app_client, owner)
    _set_profile_visibility(app_client, owner, visible=False)
    _override_photo_service(app_client)

    try:
        owner_response = app_client.get(f"/api/v1/profiles/{profile_id}", headers=_headers_for(owner))
        assert owner_response.status_code == 200
        assert owner_response.json()["data"]["visibility_tier"] == "PRIVATE"
        assert owner_response.json()["data"]["user_id"] == str(owner.id)

        unrelated_response = app_client.get(f"/api/v1/profiles/{profile_id}", headers=_headers_for(unrelated_user))
        assert unrelated_response.status_code == 404

        support_response = app_client.get(f"/api/v1/profiles/{profile_id}", headers=_headers_for(support_user))
        assert support_response.status_code == 404

        admin_response = app_client.get(f"/api/v1/profiles/{profile_id}", headers=_headers_for(admin_user))
        assert admin_response.status_code == 200
        assert admin_response.json()["data"]["visibility_tier"] == "PRIVATE"
        assert admin_response.json()["data"]["user_id"] == str(owner.id)
    finally:
        app_client.app.dependency_overrides.pop(get_photo_service, None)


def test_registered_viewer_cannot_receive_internal_profile_identifiers(app_client, make_user) -> None:
    owner = asyncio.run(make_user())
    viewer = asyncio.run(make_user())
    profile_id = _create_profile(app_client, owner)
    _override_photo_service(app_client)

    try:
        response = app_client.get(f"/api/v1/profiles/{profile_id}", headers=_headers_for(viewer))
    finally:
        app_client.app.dependency_overrides.pop(get_photo_service, None)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["visibility_tier"] == "REGISTERED"
    assert data.get("user_id") is None
    assert data.get("platform_id") is None


def test_direct_photo_list_honors_hidden_profile_authorization(app_client, make_user) -> None:
    owner = asyncio.run(make_user())
    unrelated_user = asyncio.run(make_user())
    profile_id = _create_profile(app_client, owner)
    _set_profile_visibility(app_client, owner, visible=False)
    photo_service = AsyncMock()
    photo_service.list_photos.return_value = PhotoListOut(photos=[], total=0)
    app_client.app.dependency_overrides[get_photo_service] = lambda: photo_service

    try:
        denied = app_client.get(
            f"/api/v1/profiles/{profile_id}/photos",
            headers=_headers_for(unrelated_user),
        )
        assert denied.status_code == 404
        photo_service.list_photos.assert_not_awaited()

        owner_response = app_client.get(
            f"/api/v1/profiles/{profile_id}/photos",
            headers=_headers_for(owner),
        )
    finally:
        app_client.app.dependency_overrides.pop(get_photo_service, None)

    assert owner_response.status_code == 200
    assert photo_service.list_photos.await_args.kwargs["viewer_tier"] == VisibilityTier.PRIVATE
