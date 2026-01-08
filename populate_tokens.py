
import asyncio
import secrets
from app.database import engine
from sqlalchemy import text

async def populate_tokens():
    print("Connecting to database...")
    async with engine.begin() as conn:
        try:
            print("Finding bundles with no invite_token...")
            res = await conn.execute(text("SELECT id FROM bundles WHERE invite_token IS NULL;"))
            bundle_ids = [r[0] for r in res.fetchall()]
            print(f"Found {len(bundle_ids)} bundles to update.")
            
            for bid in bundle_ids:
                token = secrets.token_urlsafe(16)
                await conn.execute(text("UPDATE bundles SET invite_token = :token WHERE id = :id"), {"token": token, "id": bid})
                print(f"Updated bundle {bid} with token.")
            
            print("Finished populating tokens.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(populate_tokens())
