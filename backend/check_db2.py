import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


async def main():
    engine = create_async_engine(settings.DATABASE_URL, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT typname FROM pg_type WHERE typname = 'admin_role_enum'"))
        print("Enum admin_role_enum:", res.fetchall())

        # Check all enums again just to be sure
        res = await conn.execute(text("SELECT t.typname, n.nspname FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace WHERE t.typtype = 'e'"))
        print("All enums with namespace:", res.fetchall())
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(main())
