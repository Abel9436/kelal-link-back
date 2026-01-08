import asyncio
from app.database import engine
from app.models import Bundle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def check():
    async with engine.begin() as conn:
        async with AsyncSession(conn) as db:
            # Check Bundle
            result = await db.execute(select(Bundle).where(Bundle.slug == 'b-ቸ'))
            bundle = result.scalar_one_or_none()
            if bundle:
                print(f'Bundle found:')
                print(f'  slug: {bundle.slug}')
                print(f'  access_level: {bundle.access_level}')
                print(f'  user_id: {bundle.user_id}')
                return
            
            print('Bundle "b-ቸ" not found in database')

asyncio.run(check())
