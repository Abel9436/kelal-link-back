import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import redis.asyncio as redis
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/urlshortener")

# Force asyncpg driver for production/managed databases
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Remove any sync-only parameters if they exist (though asyncpg is usually fine with them)
if "?sslmode=" in DATABASE_URL:
    # Some platforms add this, but asyncpg prefers the connect_args approach
    DATABASE_URL = DATABASE_URL.split("?")[0]

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Enable SSL for cloud databases (Neon, Render, etc.) but skip for local/docker
connect_args = {}
if "localhost" not in DATABASE_URL and "@db" not in DATABASE_URL:
    connect_args = {"ssl": True}

engine = create_async_engine(DATABASE_URL, echo=False, connect_args=connect_args)
async_session = async_sessionmaker(engine, expire_on_commit=False)

redis_client = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session() as session:
        yield session

async def get_redis():
    yield redis_client
