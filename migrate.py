
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

connect_args = {}
if "localhost" not in DATABASE_URL and "@db" not in DATABASE_URL:
    connect_args = {"ssl": True}

async def migrate():
    engine = create_async_engine(DATABASE_URL, connect_args=connect_args)
    
    async def add_column(table, column, type_def):
        async with engine.begin() as conn:
            try:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {type_def}"))
                print(f"Added column: {table}.{column}")
            except Exception as e:
                if "already exists" in str(e):
                    print(f"Column {table}.{column} already exists")
                else:
                    print(f"Error adding {table}.{column}: {e}")

    print("Checking for missing columns...")
    await add_column("urls", "max_clicks", "INTEGER")
    await add_column("urls", "expires_at", "TIMESTAMP WITH TIME ZONE")
    await add_column("urls", "password", "VARCHAR")
    await add_column("bundles", "theme_color", "VARCHAR DEFAULT '#00f2ff'")
    await add_column("bundles", "bg_color", "VARCHAR DEFAULT '#0a0a0a'")
    await add_column("bundles", "text_color", "VARCHAR DEFAULT '#888888'")
    await add_column("bundles", "title_color", "VARCHAR DEFAULT '#ffffff'")
    await add_column("bundles", "card_color", "VARCHAR DEFAULT 'rgba(255,255,255,0.05)'")
    await add_column("bundles", "user_id", "INTEGER REFERENCES users(id)")
    await add_column("bundles", "max_clicks", "INTEGER")
    await add_column("bundles", "expires_at", "TIMESTAMP WITH TIME ZONE")
    await add_column("bundles", "password", "VARCHAR")
    
    # Meta SEO Columns
    await add_column("urls", "meta_title", "VARCHAR")
    await add_column("urls", "meta_description", "VARCHAR")
    await add_column("bundles", "meta_title", "VARCHAR")
    await add_column("bundles", "meta_description", "VARCHAR")

    await engine.dispose()
    print("Migration complete!")
    print("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate())
