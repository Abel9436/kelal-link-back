import asyncio
from app.database import engine
from app.models import URL, Bundle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def check():
    async with engine.begin() as conn:
        async with AsyncSession(conn) as db:
            # Check URL
            result = await db.execute(select(URL).where(URL.slug == 'kjh'))
            url = result.scalar_one_or_none()
            if url:
                print(f'URL found:')
                print(f'  slug: {url.slug}')
                print(f'  is_cloaked: {url.is_cloaked}')
                print(f'  user_id: {url.user_id}')
                print(f'  long_url: {url.long_url}')
                return
            
            # Check Bundle
            result = await db.execute(select(Bundle).where(Bundle.slug == 'kjh'))
            bundle = result.scalar_one_or_none()
            if bundle:
                print(f'Bundle found:')
                print(f'  slug: {bundle.slug}')
                print(f'  is_cloaked: {bundle.is_cloaked}')
                print(f'  access_level: {bundle.access_level}')
                print(f'  user_id: {bundle.user_id}')
                return
            
            print('Slug "kjh" not found in database')

asyncio.run(check())
