import asyncio
from sqlalchemy import inspect
from app import database, models

async def run():
    async with database.engine.connect() as conn:
        def get_cols(sync_conn):
            return inspect(sync_conn).get_columns('clicks')
        columns = await conn.run_sync(get_cols)
        print(f"Clicks columns: {[c['name'] for c in columns]}")

if __name__ == "__main__":
    asyncio.run(run())
