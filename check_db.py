
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
        res = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'bundles'"))
        columns = [row[0] for row in res.fetchall()]
        print(f"Columns in bundles: {columns}")
        
        res = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'urls'"))
        columns = [row[0] for row in res.fetchall()]
        print(f"Columns in urls: {columns}")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())
