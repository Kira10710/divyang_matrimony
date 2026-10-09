import asyncio
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.enums import GenderEnum, MaritalStatusEnum
from app.models.partner_preference import PartnerPreference


async def run():
    engine = create_async_engine('postgresql+asyncpg://divyang:devpassword@localhost:5432/divyang_matrimony')
    async_session = async_sessionmaker(engine)
    async with async_session() as session:
        profile_id = uuid.uuid4()
        user_id = uuid.uuid4()
        await session.execute(text(f"INSERT INTO users (id, phone, platform_id) VALUES ('{user_id}', '+919999999999', 'divyang_matrimony')"))
        await session.execute(text(f"INSERT INTO profiles (id, user_id, platform_id, first_name, last_name, gender, date_of_birth, marital_status, country) VALUES ('{profile_id}', '{user_id}', 'divyang_matrimony', 'T', 'T', 'MALE', '1990-01-01', 'NEVER_MARRIED', 'India')"))

        pref = PartnerPreference(
            profile_id=profile_id,
            preferred_marital_statuses=[MaritalStatusEnum.NEVER_MARRIED],
            preferred_gender=GenderEnum.FEMALE
        )
        session.add(pref)
        await session.commit()

        print('Postgres insert success!')

        await session.execute(text(f"DELETE FROM users WHERE id='{user_id}';"))
        await session.commit()

asyncio.run(run())
