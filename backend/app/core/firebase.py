"""
Firebase Admin SDK client — lazy singleton.

Initialised once on first use from `FIREBASE_CREDENTIALS_PATH` and
`FIREBASE_STORAGE_BUCKET` in settings. Every subsequent call returns
the already-initialised app (firebase_admin raises an error if you
initialise twice, which we guard against).

Architecture §4.2, §7:
  - Bucket is PRIVATE. Callers must request a short-lived signed URL for
    every read (TTL = PHOTO_SIGNED_URL_TTL_SECONDS, default 15 min).
  - Long-lived Firebase download URLs are never issued — they bypass
    server-side privacy-tier checks.

Usage (dependency-injected via get_storage_bucket):
    bucket = get_storage_bucket()
    blob  = bucket.blob(storage_path)
    url   = blob.generate_signed_url(expiration=timedelta(minutes=15), ...)
"""
from __future__ import annotations

import firebase_admin
import structlog
from firebase_admin import credentials, storage
from google.oauth2 import service_account

from app.core.config import settings

logger = structlog.get_logger(__name__)

_firebase_app: firebase_admin.App | None = None


def _init_firebase() -> firebase_admin.App:
    """Initialise Firebase Admin SDK once; return the app."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    _firebase_app = firebase_admin.initialize_app(
        cred,
        {"storageBucket": settings.FIREBASE_STORAGE_BUCKET},
    )
    logger.info("firebase_admin.initialised", bucket=settings.FIREBASE_STORAGE_BUCKET)
    return _firebase_app


def get_storage_bucket() -> storage.storage.Bucket:  # type: ignore[name-defined]
    """
    Return the Firebase Storage bucket handle.

    Initialises the Firebase app on the first call. Safe to call from
    multiple coroutines — the global guard and GIL make it race-free
    for this single-writer pattern.
    """
    _init_firebase()
    return storage.bucket()


def get_gcs_credentials() -> service_account.Credentials:
    """
    Return google-auth credentials scoped for GCS signed-URL generation.

    Firebase Admin's storage.bucket().blob().generate_signed_url() requires
    either Application Default Credentials with signing permission or an
    explicit service-account credentials object. We reuse the same service
    account JSON used for firebase_admin initialisation.
    """
    return service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
        settings.FIREBASE_CREDENTIALS_PATH,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
