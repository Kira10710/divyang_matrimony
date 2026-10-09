import asyncio
from redis.asyncio import Redis

async def main():
    r = Redis.from_url("redis://localhost:6379/0")
    keys = await r.keys("*")
    print(keys)
    await r.aclose()

asyncio.run(main())
