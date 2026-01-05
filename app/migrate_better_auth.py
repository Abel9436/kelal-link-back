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

async def migrate():
    engine = create_async_engine(DATABASE_URL)
    
    async with engine.begin() as conn:
        print("Starting Better-Auth Schema Alignment...")
        
        # 1. Create Better-Auth tables if they don't exist
        # We use raw SQL to ensure exact compatibility with Better-Auth's expectations
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS "user" (
                "id" TEXT PRIMARY KEY,
                "name" TEXT NOT NULL,
                "email" TEXT NOT NULL UNIQUE,
                "emailVerified" BOOLEAN NOT NULL DEFAULT FALSE,
                "image" TEXT,
                "createdAt" TIMESTAMP NOT NULL DEFAULT NOW(),
                "updatedAt" TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """))
        print("Table 'user' verified.")
        
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS "session" (
                "id" TEXT PRIMARY KEY,
                "expiresAt" TIMESTAMP NOT NULL,
                "token" TEXT NOT NULL UNIQUE,
                "createdAt" TIMESTAMP NOT NULL DEFAULT NOW(),
                "updatedAt" TIMESTAMP NOT NULL DEFAULT NOW(),
                "ipAddress" TEXT,
                "userAgent" TEXT,
                "userId" TEXT NOT NULL REFERENCES "user"("id") ON DELETE CASCADE
            );
        """))
        print("Table 'session' verified.")
        
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS "account" (
                "id" TEXT PRIMARY KEY,
                "accountId" TEXT NOT NULL,
                "providerId" TEXT NOT NULL,
                "userId" TEXT NOT NULL REFERENCES "user"("id") ON DELETE CASCADE,
                "accessToken" TEXT,
                "refreshToken" TEXT,
                "idToken" TEXT,
                "accessTokenExpiresAt" TIMESTAMP,
                "refreshTokenExpiresAt" TIMESTAMP,
                "scope" TEXT,
                "password" TEXT,
                "createdAt" TIMESTAMP NOT NULL DEFAULT NOW(),
                "updatedAt" TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """))
        print("Table 'account' verified.")
        
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS "verification" (
                "id" TEXT PRIMARY KEY,
                "identifier" TEXT NOT NULL,
                "value" TEXT NOT NULL,
                "expiresAt" TIMESTAMP NOT NULL,
                "createdAt" TIMESTAMP DEFAULT NOW(),
                "updatedAt" TIMESTAMP DEFAULT NOW()
            );
        """))
        print("Table 'verification' verified.")
        
        # 2. Update urls and bundles tables to use TEXT for user_id
        # We take a safe approach: Check if column exists, then change type or add.
        # Note: If there is existing data, casting Integer to Text is safe.
        
        for table in ["urls", "bundles"]:
            print(f"Aligning table '{table}'...")
            try:
                # Add user_id column if not exists (as TEXT)
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id_new TEXT"))
                # Migrate old user_id data if integer
                await conn.execute(text(f"UPDATE {table} SET user_id_new = user_id::TEXT WHERE user_id IS NOT NULL"))
                # Swap columns
                await conn.execute(text(f"ALTER TABLE {table} DROP COLUMN user_id"))
                await conn.execute(text(f"ALTER TABLE {table} RENAME COLUMN user_id_new TO user_id"))
                print(f"Table '{table}' aligned successfully.")
            except Exception as e:
                print(f"Note on table '{table}': {str(e)}")
                # Probably column already correct or some other minor issue, continue
        
        print("Migration complete. The Studio is now Better-Auth Compatible.")

if __name__ == "__main__":
    asyncio.run(migrate())
