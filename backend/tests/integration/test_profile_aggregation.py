import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

@pytest.fixture
def test_profile_headers(app_client, fake_redis, make_user) -> dict:
    import asyncio

    from app.core.security import create_access_token
    user = asyncio.run(make_user())
    token = create_access_token(str(user.id), str(user.platform_id))
    headers = {"Authorization": f"Bearer {token}"}
    response = app_client.post(
        "/api/v1/profiles",
        headers=headers,
        json={
            "first_name": "Agg",
            "last_name": "User",
            "gender": "MALE",
            "date_of_birth": "1990-01-01",
            "marital_status": "NEVER_MARRIED",
            "disability_type": "PHYSICAL"
        }
    )
    if response.status_code != 201:
        print("ERROR CREATING PROFILE:", response.json())
    assert response.status_code == 201
    return headers

async def test_get_own_profile_aggregation(
    app_client: AsyncClient,
    test_profile_headers: dict,
    db_session
):
    import uuid
    from datetime import datetime
    from unittest.mock import AsyncMock

    from app.core.dependencies import get_photo_service
    from app.models.enums import ModerationStatusEnum
    from app.schemas.photo import PhotoListOut, PhotoOut

    mock_photo_svc = AsyncMock()
    # Initial empty photos
    mock_photo_svc.list_photos.return_value = PhotoListOut(photos=[], total=0)
    app_client.app.dependency_overrides[get_photo_service] = lambda: mock_photo_svc

    try:
        response = app_client.get("/api/v1/profiles/me", headers=test_profile_headers)
        assert response.status_code == 200
        data = response.json()["data"]

        # Check aggregation
        assert "profile" in data
        assert "sensitive_data" in data
        assert "partner_preferences" in data
        assert "photos" in data["profile"]

        # Partner preferences should be None initially
        assert data["partner_preferences"] is None

        # Photos should be empty list initially
        assert data["profile"]["photos"] == []

        # Now let's create a partner preference
        pref_response = app_client.put(
            "/api/v1/profiles/me/partner-preferences",
            headers=test_profile_headers,
            json={"age_min": 25, "age_max": 35}
        )
        assert pref_response.status_code == 200

        # Let's add a photo (Note: POST actually depends on real photo service which we mocked!)
        # So it will hit the mock. We don't care, we just need to update the mock return value.
        mock_photo_svc.list_photos.return_value = PhotoListOut(
            photos=[
                PhotoOut(
                    id=uuid.uuid4(),
                    profile_id=uuid.uuid4(),
                    display_order=0,
                    is_primary=False,
                    moderation_status=ModerationStatusEnum.PENDING,
                    created_at=datetime.utcnow()
                )
            ],
            total=1
        )

        # Fetch aggregate again
        response = app_client.get("/api/v1/profiles/me", headers=test_profile_headers)
        assert response.status_code == 200
        data = response.json()["data"]

        assert data["partner_preferences"] is not None
        assert data["partner_preferences"]["age_min"] == 25

        assert len(data["profile"]["photos"]) == 1
        assert data["profile"]["photos"][0]["moderation_status"] == "PENDING"
    finally:
        app_client.app.dependency_overrides.pop(get_photo_service, None)
