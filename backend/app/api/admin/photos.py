"""
Admin Photos API routes.

Provides endpoints for photo moderation:
- GET /api/admin/photos/moderation-queue
- PUT /api/admin/photos/{photo_id}/approve
- PUT /api/admin/photos/{photo_id}/reject
"""
import uuid

import structlog
from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_photo_service, require_any_admin
from app.core.response import success_response
from app.models.user import User
from app.schemas.photo import PhotoModerationRejectRequest
from app.services.photo_service import PhotoService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/photos", tags=["Admin Photos"])


@router.get(
    "/moderation-queue",
    status_code=status.HTTP_200_OK,
    summary="Get pending photos",
    description="Returns a list of photos awaiting moderation.",
)
async def get_moderation_queue(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_admin: User = Depends(require_any_admin()),
    photo_svc: PhotoService = Depends(get_photo_service),
) -> dict:
    result = await photo_svc.get_moderation_queue(limit=limit, offset=offset)
    return success_response(
        data=result.model_dump(mode="json"),
        message="Moderation queue retrieved",
    )


@router.put(
    "/{photo_id}/approve",
    status_code=status.HTTP_200_OK,
    summary="Approve photo",
    description="Approves a pending photo.",
)
async def approve_photo(
    photo_id: uuid.UUID,
    current_admin: User = Depends(require_any_admin()),
    photo_svc: PhotoService = Depends(get_photo_service),
) -> dict:
    result = await photo_svc.approve_photo(photo_id)
    logger.info(
        "admin.photo_approved",
        admin_id=str(current_admin.id),
        photo_id=str(photo_id),
    )
    return success_response(
        data=result.model_dump(mode="json"),
        message="Photo approved successfully",
    )


@router.put(
    "/{photo_id}/reject",
    status_code=status.HTTP_200_OK,
    summary="Reject photo",
    description="Rejects a pending photo with a reason.",
)
async def reject_photo(
    photo_id: uuid.UUID,
    body: PhotoModerationRejectRequest,
    current_admin: User = Depends(require_any_admin()),
    photo_svc: PhotoService = Depends(get_photo_service),
) -> dict:
    result = await photo_svc.reject_photo(photo_id, body.rejection_reason)
    logger.info(
        "admin.photo_rejected",
        admin_id=str(current_admin.id),
        photo_id=str(photo_id),
        reason=body.rejection_reason,
    )
    return success_response(
        data=result.model_dump(mode="json"),
        message="Photo rejected successfully",
    )
