
import asyncio
from sqlalchemy import text
from app.database import engine
import secrets

async def upgrade_db():
    print("Connecting to database...")
    async with engine.begin() as conn:
        try:
            print("Adding manager_token and analyst_token columns...")
            await conn.execute(text("ALTER TABLE bundles ADD COLUMN IF NOT EXISTS manager_token VARCHAR;"))
            await conn.execute(text("ALTER TABLE bundles ADD COLUMN IF NOT EXISTS analyst_token VARCHAR;"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_bundles_manager_token ON bundles (manager_token);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_bundles_analyst_token ON bundles (analyst_token);"))
            
            print("Migrating existing data...")
            res = await conn.execute(text("SELECT id, invite_token FROM bundles;"))
            rows = res.fetchall()
            for bid, old_token in rows:
                m_token = old_token or secrets.token_urlsafe(16)
                a_token = secrets.token_urlsafe(16)
                await conn.execute(text("UPDATE bundles SET manager_token = :m, analyst_token = :a WHERE id = :id"), {"m": m_token, "a": a_token, "id": bid})
            
            print("Removing old invite_token column...")
            await conn.execute(text("ALTER TABLE bundles DROP COLUMN IF EXISTS invite_token;"))
            
            print("Successfully upgraded database.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(upgrade_db())
