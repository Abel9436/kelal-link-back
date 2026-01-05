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

async def revert():
    engine = create_async_engine(DATABASE_URL)
    
    async with engine.begin() as conn:
        print("Starting Better-Auth Reversion Protocol...")
        
        # 1. Create standard users table if it doesn't exist
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS "users" (
                "id" SERIAL PRIMARY KEY,
                "email" TEXT NOT NULL UNIQUE,
                "name" TEXT,
                "profile_pic" TEXT,
                "google_id" TEXT UNIQUE NOT NULL,
                "created_at" TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """))
        print("Table 'users' (canonical) verified.")
        
        # 2. Sync data from Better-Auth 'user' table if possible
        try:
            # We try to migrate users back
            await conn.execute(text("""
                INSERT INTO "users" (email, name, profile_pic, google_id)
                SELECT email, name, image as profile_pic, id as google_id
                FROM "user"
                ON CONFLICT (email) DO UPDATE SET
                    name = EXCLUDED.name,
                    profile_pic = EXCLUDED.profile_pic,
                    google_id = EXCLUDED.google_id;
            """))
            print("Creators migrated back to 'users' table.")
        except Exception as e:
            print(f"Skipping user data migration: {e}")
        
        # 3. Clean up Better-Auth tables
        for table in ["session", "account", "verification", "user"]:
            try:
                await conn.execute(text(f"DROP TABLE IF EXISTS \"{table}\" CASCADE"))
                print(f"Purged Better-Auth table: {table}")
            except Exception as e:
                print(f"Could not purge table {table}: {e}")
        
        # 4. Revert urls and bundles user_id to INTEGER
        for table in ["urls", "bundles"]:
            print(f"Reverting table '{table}' user_id...")
            try:
                # We need to map the string IDs back to the new serial IDs in 'users'
                # This is complex because we just recreated IDs. 
                # But typically creators will just log in again.
                # To be helpful, we'll try to match by google_id string which we stored in "google_id" field of "users"
                
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id_new INTEGER"))
                
                # Update new user_id by matching the old string ID (google_id)
                await conn.execute(text(f"""
                    UPDATE {table} t
                    SET user_id_new = u.id
                    FROM users u
                    WHERE t.user_id = u.google_id
                """))
                
                # Drop old TEXT column and replace with new INTEGER column
                await conn.execute(text(f"ALTER TABLE {table} DROP COLUMN user_id"))
                await conn.execute(text(f"ALTER TABLE {table} RENAME COLUMN user_id_new TO user_id"))
                await conn.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT {table}_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id)"))
                
                print(f"Table '{table}' reverted to Integer identity successfully.")
            except Exception as e:
                print(f"Note on table '{table}': {str(e)}")

        print("Reversion complete. The Studio is back to its 'Normal' Identity Handshake.")

if __name__ == "__main__":
    asyncio.run(revert())
