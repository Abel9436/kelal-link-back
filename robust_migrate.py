import asyncio
import secrets
from sqlalchemy import text, inspect
from app.database import engine
from sqlalchemy.ext.asyncio import AsyncSession

async def upgrade_db():
    print("🚀 Starting Database Pulse Sync...")
    async with engine.begin() as conn:
        # Get column info
        def get_columns(connection, table_name):
            # This is a bit tricky in async, we use sync execution for inspector if needed 
            # or just raw SQL which is more reliable across dialects
            return []

        # Use raw SQL to check columns for PostgreSQL/SQLite compatibility
        res = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'bundles'"
        ))
        existing_cols = [r[0] for r in res.fetchall()]
        
        # 1. Add manager_token
        if "manager_token" not in existing_cols:
            print("  [+] Adding manager_token column...")
            await conn.execute(text("ALTER TABLE bundles ADD COLUMN manager_token VARCHAR;"))
            await conn.execute(text("CREATE INDEX ix_bundles_manager_token ON bundles (manager_token);"))
        
        # 2. Add analyst_token
        if "analyst_token" not in existing_cols:
            print("  [+] Adding analyst_token column...")
            await conn.execute(text("ALTER TABLE bundles ADD COLUMN analyst_token VARCHAR;"))
            await conn.execute(text("CREATE INDEX ix_bundles_analyst_token ON bundles (analyst_token);"))

        # 3. Handle data migration if invite_token exists
        if "invite_token" in existing_cols:
            print("  [~] Migrating data from legacy invite_token...")
            res = await conn.execute(text("SELECT id, invite_token FROM bundles WHERE manager_token IS NULL;"))
            rows = res.fetchall()
            for bid, old_token in rows:
                m_token = old_token or secrets.token_urlsafe(16)
                a_token = secrets.token_urlsafe(16)
                await conn.execute(text(
                    "UPDATE bundles SET manager_token = :m, analyst_token = :a WHERE id = :id"
                ), {"m": m_token, "a": a_token, "id": bid})
            
            print("  [-] DROPPING legacy invite_token column...")
            await conn.execute(text("ALTER TABLE bundles DROP COLUMN invite_token;"))
        else:
            # Check for any bundles that somehow missing tokens
            print("  [~] Ensuring all bundles have secure tokens...")
            res = await conn.execute(text("SELECT id FROM bundles WHERE manager_token IS NULL OR analyst_token IS NULL;"))
            rows = res.fetchall()
            for (bid,) in rows:
                m_token = secrets.token_urlsafe(16)
                a_token = secrets.token_urlsafe(16)
                await conn.execute(text(
                    "UPDATE bundles SET manager_token = :m, analyst_token = :a WHERE id = :id"
                ), {"m": m_token, "a": a_token, "id": bid})

    print("✅ Database Pulse Sync Complete. Systems nominal.")

if __name__ == "__main__":
    asyncio.run(upgrade_db())
