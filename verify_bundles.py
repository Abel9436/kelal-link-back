
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/urlshortener")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

async def check():
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        try:
            res = await conn.execute(text("SELECT id, theme_color FROM bundles"))
            data = res.fetchall()
            print(f"Bundles theme_colors: {data}")
        except Exception as e:
            print(f"Error checking bundles: {e}")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())
