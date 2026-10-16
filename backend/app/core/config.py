"""
Application configuration via Pydantic BaseSettings.

All secrets and environment-specific values are loaded from environment
variables (or .env in development). No secret has a default value —
the app fails to start if a required secret is missing.

See Architecture Section 3.2.
"""
import os
import re
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings

_PLACEHOLDER_MARKERS = (
    "changeme", "change-me", "change_me", "your-", "example", "placeholder",
    "not-for-production", "do-not-use", "devpassword", "unit-test",
)


class Settings(BaseSettings):
    """Application settings — loaded from environment variables."""

    # --- Environment ---
    ENVIRONMENT: Literal["development", "staging", "production"]  # REQUIRED
    LOG_LEVEL: str = "INFO"
    PLATFORM_ID: str = "divyang_matrimony"

    # --- Database ---
    DATABASE_URL: str  # postgresql+asyncpg://user:pass@host:port/db

    # --- Redis (cache + rate-limit only in v1) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- JWT ---
    JWT_SECRET_KEY: str  # REQUIRED — no default
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15   # Short-lived access tokens
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30     # Long-lived refresh tokens

    # --- OTP ---
    OTP_EXPIRE_SECONDS: int = 300               # 5 minutes
    OTP_LENGTH: int = 6
    OTP_MAX_ATTEMPTS: int = 3                   # Max wrong guesses before OTP is invalidated
    OTP_RATE_LIMIT_PER_HOUR: int = 5            # Max OTP sends per phone per hour
    OTP_IP_RATE_LIMIT_PER_HOUR: int = 20        # Max OTP sends per IP per hour
    OTP_GLOBAL_RATE_LIMIT_PER_MINUTE: int = 60  # Global safety cap per platform per minute

    # --- Auth rate limits (Architecture §7.7) ---
    # Account-based lockout (per phone/email per platform):
    AUTH_MAX_FAILED_ATTEMPTS: int = 5
    AUTH_LOCKOUT_SECONDS: int = 900             # 15 minutes
    AUTH_LOCKOUT_WINDOW_SECONDS: int = 900      # Sliding window for failed attempts
    AUTH_ADMIN_IP_RATE_LIMIT: int = 10          # Max admin login attempts per IP per 15 minutes

    # --- Field-level encryption (Database.md §3.3) ---
    FIELD_ENCRYPTION_KEY: str  # REQUIRED — hex-encoded 32-byte AES-256 key (64 hex chars)
    # Generate: python -c "import os; print(os.urandom(32).hex())"

    # --- Firebase ---
    FIREBASE_CREDENTIALS_PATH: str  # Path to service account JSON file
    FIREBASE_STORAGE_BUCKET: str

    # --- Photos (Architecture §4.2) ---
    PHOTO_MAX_SIZE_MB: int = 10          # Reject uploads larger than this (per variant)
    # Decode limits. The client sends <= ~1600 px (about 2.6 MP); 12 MP leaves headroom for
    # direct API clients while bounding decoded memory (about 36 MB per RGB frame, see Architecture §7.9).
    PHOTO_MAX_PIXELS: int = 12_000_000
    PHOTO_PROCESSING_CONCURRENCY: int = 1  # Images processed at once; raise only with more RAM
    PHOTO_SIGNED_URL_TTL_SECONDS: int = 900  # Signed read URL lifetime (15 min)

    # --- Razorpay (sandbox for v1) ---
    RAZORPAY_KEY_ID: str
    RAZORPAY_KEY_SECRET: str
    RAZORPAY_WEBHOOK_SECRET: str

    # --- Sentry ---
    SENTRY_DSN: str = ""

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    # --- Reverse proxy ---
    # Number of trusted proxies in front of the app. 0 = ignore X-Forwarded-For and use the
    # socket peer. With N > 0 the client IP is the Nth entry from the right of X-Forwarded-For,
    # so entries a client prepends cannot spoof it. Measure the real hop count before setting it.
    TRUSTED_PROXY_HOPS: int = 0

    # --- Database pool (per process) ---
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    @model_validator(mode="after")
    def _validate_deployed_configuration(self) -> "Settings":
        """Refuse to start a staging/production process with unsafe configuration.

        Messages name the setting and the rule, never the value.
        """
        if not 0 <= self.TRUSTED_PROXY_HOPS <= 5:
            raise ValueError("TRUSTED_PROXY_HOPS must be between 0 and 5")
        if self.PHOTO_MAX_PIXELS < 1 or self.PHOTO_PROCESSING_CONCURRENCY < 1:
            raise ValueError("PHOTO_MAX_PIXELS and PHOTO_PROCESSING_CONCURRENCY must be positive")
        if self.ENVIRONMENT == "development":
            return self

        problems: list[str] = []
        jwt_key = self.JWT_SECRET_KEY
        if len(jwt_key) < 32 or len(set(jwt_key)) < 10:
            problems.append("JWT_SECRET_KEY must be at least 32 characters of random data")
        if any(marker in jwt_key.lower() for marker in _PLACEHOLDER_MARKERS):
            problems.append("JWT_SECRET_KEY looks like a placeholder")
        if self.JWT_ALGORITHM not in ("HS256", "HS384", "HS512"):
            problems.append("JWT_ALGORITHM must be an HMAC algorithm (HS256/HS384/HS512)")

        enc = self.FIELD_ENCRYPTION_KEY
        if not re.fullmatch(r"[0-9a-fA-F]{64}", enc) or len(set(enc.lower())) < 8:
            problems.append("FIELD_ENCRYPTION_KEY must be 64 random hex characters (not a repeated pattern)")

        if "CORS_ORIGINS" not in self.model_fields_set:
            problems.append("CORS_ORIGINS must be set explicitly")
        for origin in self.CORS_ORIGINS:
            if origin.strip() == "*" or not origin.startswith("https://"):
                problems.append("CORS_ORIGINS entries must be explicit https:// origins (no '*')")
                break
        if "REDIS_URL" not in self.model_fields_set:
            problems.append("REDIS_URL must be set explicitly")

        if not self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            problems.append("DATABASE_URL must be a postgresql+asyncpg:// URL")
        if any(marker in self.DATABASE_URL.lower() for marker in ("devpassword", ":test@")):
            problems.append("DATABASE_URL uses a development/test credential")

        if not self.FIREBASE_STORAGE_BUCKET.strip():
            problems.append("FIREBASE_STORAGE_BUCKET must be set")
        if not os.path.isfile(self.FIREBASE_CREDENTIALS_PATH):
            problems.append("FIREBASE_CREDENTIALS_PATH must point to an existing service-account file")

        if problems:
            raise ValueError("Unsafe " + self.ENVIRONMENT + " configuration: " + "; ".join(problems))
        return self

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()  # type: ignore[call-arg]
