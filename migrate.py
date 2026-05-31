"""Run database migrations on startup."""
import asyncio
from sqlalchemy import text
from main import engine, Base

async def run():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Migrations complete.")

if __name__ == "__main__":
    asyncio.run(run())
