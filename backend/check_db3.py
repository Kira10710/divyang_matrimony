import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


async def main():
    print("Connecting to:", settings.DATABASE_URL)
    engine = create_async_engine(settings.DATABASE_URL, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT typname FROM pg_type WHERE typtype = 'e'"))
        enums = [r[0] for r in res.fetchall()]
        print("Enums:", enums)

        res = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
        tables = [r[0] for r in res.fetchall()]
        print("Tables:", tables)
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(main())
