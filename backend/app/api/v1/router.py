"""
v1 API router — aggregates all feature routers under /api/v1.

See Architecture Section 6 for the full endpoint list.
"""
from fastapi import APIRouter

from app.api.v1 import auth, partner_preferences, photos, profiles

# TODO: Import remaining feature routers as they are implemented
# from app.api.v1 import search
# from app.api.v1 import interests, matching, payments, subscriptions
# from app.api.v1 import notifications, reports, settings, verification
# from app.api.v1 import webhooks, analytics

router = APIRouter(prefix="/api/v1")

# auth.py already defines its own `/auth` prefix (see app/api/v1/auth.py),
# so it isn't repeated here.
router.include_router(auth.router)

# Profile module (Phase 4.1)
router.include_router(profiles.router)
router.include_router(partner_preferences.router)

# Photo module (Phase 4.2)
router.include_router(photos.router)

# TODO: Include remaining feature routers:
# router.include_router(search.router, prefix="/search", tags=["Search"])
# router.include_router(interests.router, prefix="/interests", tags=["Interests"])
# router.include_router(matching.router, prefix="/matching", tags=["Matching"])
# router.include_router(payments.router, prefix="/payments", tags=["Payments"])
# router.include_router(subscriptions.router, prefix="/subscriptions", tags=["Subscriptions"])
# router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
# router.include_router(reports.router, prefix="/reports", tags=["Reports"])
# router.include_router(settings.router, prefix="/settings", tags=["Settings"])
# router.include_router(verification.router, prefix="/verifications", tags=["Verification"])
# router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
# router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])



@router.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for uptime monitoring."""
    return {"status": "healthy"}
