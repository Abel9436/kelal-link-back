import asyncio
from sqlalchemy import select
from app import models, database

async def check():
    async for db in database.get_db():
        res = await db.execute(select(models.URL))
        urls = res.scalars().all()
        print(f"URLs: {[u.slug for u in urls]}")
        
        res = await db.execute(select(models.Bundle))
        bundles = res.scalars().all()
        print(f"Bundles: {[b.slug for b in bundles]}")
        break

if __name__ == "__main__":
    asyncio.run(check())
