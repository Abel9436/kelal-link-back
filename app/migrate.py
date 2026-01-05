import asyncio
from sqlalchemy import text
from app.database import engine
from app import models

async def migrate():
    print("Initiating Studio Schema Upgrade...")
    
    # Ensure users table
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    
    # URLs Table
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE urls ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)"))
            print("Done with URLs check.")
        except Exception as e:
            print(f"URLs Table error: {e}")

    # Bundles Table
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE bundles ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id)"))
            print("Done with Bundles check.")
        except Exception as e:
            print(f"Bundles Table error: {e}")

    print("Migration Process Finished.")

if __name__ == "__main__":
    asyncio.run(migrate())
