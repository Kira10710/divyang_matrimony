import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


async def main():
    engine = create_async_engine(settings.DATABASE_URL, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        # Check alembic_version
        try:
            res = await conn.execute(text("SELECT * FROM alembic_version"))
            print("alembic_version:", res.fetchall())
        except Exception as e:
            print("alembic_version:", str(e))

        # Check tables
        res = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
        print("Tables:", [r[0] for r in res.fetchall()])

        # Check enums
        res = await conn.execute(text("SELECT typname FROM pg_type WHERE typtype = 'e'"))
        print("Enums:", [r[0] for r in res.fetchall()])

    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(main())
