"""
SQLAlchemy async engine and session factory.

Provides:
- Async engine connected to DATABASE_URL
- Session factory (async_sessionmaker) for request-scoped sessions
- Base declarative class with common mixins

See Architecture Section 3.1 and 3.3.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.ENVIRONMENT == "development"),
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """
    Dependency that yields an async DB session per request.

    Auto-rolls-back on exception, auto-closes after use.
    Usage: db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
