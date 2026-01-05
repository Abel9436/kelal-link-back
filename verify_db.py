
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/urlshortener")

async def verify():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='urls'"))
        columns = [row[0] for row in result.fetchall()]
        print("DATABASE_COLUMNS_START")
        for col in columns:
            print(f"COL: {col}")
        print("DATABASE_COLUMNS_END")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(verify())
