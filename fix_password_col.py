
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/urlshortener")

async def migrate_password():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        print("Attempting to add 'password' column...")
        try:
            # PostgreSQL syntax: ALTER TABLE name ADD COLUMN IF NOT EXISTS colname type
            await conn.execute(text("ALTER TABLE urls ADD COLUMN IF NOT EXISTS password VARCHAR"))
            print("Migration successful: 'password' column added or already exists.")
        except Exception as e:
            print(f"FAILED to add password column: {str(e)}")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate_password())
