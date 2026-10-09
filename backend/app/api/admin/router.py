"""
Admin API router — aggregates all admin-facing routers under /api/admin.

All routes require admin authentication.
See Architecture Section 6.13 and Section 7.8 for role hierarchy.
"""
from fastapi import APIRouter

# TODO: Import individual admin routers as they are implemented
# from app.api.admin import dashboard, users, reports, payments, verification, analytics

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# TODO: Include admin routers:
# router.include_router(dashboard.router, prefix="/dashboard", tags=["Admin Dashboard"])
# router.include_router(users.router, prefix="/users", tags=["Admin Users"])
# router.include_router(reports.router, prefix="/reports", tags=["Admin Reports"])
# router.include_router(payments.router, prefix="/payments", tags=["Admin Payments"])
# router.include_router(verification.router, prefix="/verifications", tags=["Admin Verification"])
# router.include_router(analytics.router, prefix="/analytics", tags=["Admin Analytics"])

from app.api.admin import photos

router.include_router(photos.router)
