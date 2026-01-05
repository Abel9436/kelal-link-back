
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from .database import Base, DATABASE_URL

async def migrate():
    print(f"Connecting to: {DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        print("Creating all missing tables...")
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
