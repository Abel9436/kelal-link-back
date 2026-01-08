import asyncio
from app.database import engine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def check():
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'bundles'"))
        columns = [r[0] for r in res.fetchall()]
        print("Columns in 'bundles' table:")
        for col in columns:
            print(f"  - {col}")

if __name__ == "__main__":
    asyncio.run(check())
