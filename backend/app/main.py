"""
Divyang Matrimony — FastAPI Application Factory.

Creates and configures the FastAPI app instance with:
- CORS middleware
- Request ID + timing middleware
- Exception handlers
- API routers (v1 + admin)
- Lifespan events (DB pool, Redis, scheduler)

See Architecture Section 3.1.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin.router import router as admin_router
from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging_config import setup_logging
from app.core.middleware import RequestIDMiddleware, TimingMiddleware
from app.core.redis import close_redis, init_redis
from app.core.scheduler import init_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # --- Startup ---
    setup_logging()
    await init_redis()
    init_scheduler()

    yield

    # --- Shutdown ---
    shutdown_scheduler()
    await close_redis()


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="Divyang Matrimony API",
        description="Backend API for the Divyang Matrimony platform",
        version="1.0.0",
        docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None,
        lifespan=lifespan,
    )

    # --- Middleware (order matters: outermost first) ---
    # In development, allow any localhost port so Flutter web's random debug
    # port is always accepted. Production uses the explicit CORS_ORIGINS list.
    cors_kwargs: dict = {
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    if settings.ENVIRONMENT == "development":
        cors_kwargs["allow_origin_regex"] = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
    else:
        cors_kwargs["allow_origins"] = settings.CORS_ORIGINS
    app.add_middleware(CORSMiddleware, **cors_kwargs)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(TimingMiddleware)

    # --- Exception Handlers ---
    register_exception_handlers(app)

    # --- Routers ---
    app.include_router(v1_router)
    app.include_router(admin_router)

    # --- Root health check (also available at /api/v1/health) ---
    @app.get("/health", tags=["Health"], include_in_schema=False)
    async def root_health():
        return {"status": "healthy"}

    return app


app = create_app()
