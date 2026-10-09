"""
Application configuration via Pydantic BaseSettings.

All secrets and environment-specific values are loaded from environment
variables (or .env in development). No secret has a default value —
the app fails to start if a required secret is missing.

See Architecture Section 3.2.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings — loaded from environment variables."""

    # --- Environment ---
    ENVIRONMENT: str = "development"  # development | staging | production
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

    # --- Auth rate limits (Architecture §7.7) ---
    # Account-based lockout (per phone/email per platform):
    AUTH_MAX_FAILED_ATTEMPTS: int = 5
    AUTH_LOCKOUT_SECONDS: int = 900             # 15 minutes
    AUTH_LOCKOUT_WINDOW_SECONDS: int = 900      # Sliding window for failed attempts

    # --- Field-level encryption (Database.md §3.3) ---
    FIELD_ENCRYPTION_KEY: str  # REQUIRED — hex-encoded 32-byte AES-256 key (64 hex chars)
    # Generate: python -c "import os; print(os.urandom(32).hex())"

    # --- Firebase ---
    FIREBASE_CREDENTIALS_PATH: str  # Path to service account JSON file
    FIREBASE_STORAGE_BUCKET: str

    # --- Photos (Architecture §4.2) ---
    PHOTO_MAX_SIZE_MB: int = 10          # Reject uploads larger than this (per variant)
    PHOTO_SIGNED_URL_TTL_SECONDS: int = 900  # Signed read URL lifetime (15 min)

    # --- Razorpay (sandbox for v1) ---
    RAZORPAY_KEY_ID: str
    RAZORPAY_KEY_SECRET: str
    RAZORPAY_WEBHOOK_SECRET: str

    # --- Sentry ---
    SENTRY_DSN: str = ""

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()  # type: ignore[call-arg]
