
import asyncio
import os
import sys

# Add the parent directory to sys.path so we can import from 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine, DATABASE_URL
from app.models import URL, Bundle, Click # Ensure they are registered

async def migrate():
    print(f"Connecting to: {DATABASE_URL}")
    async with engine.begin() as conn:
        print("Creating all missing tables...")
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
