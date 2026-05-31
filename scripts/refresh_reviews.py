"""Re-fetch reviews for restaurants whose review cache has expired."""
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.models.review_cache import ReviewCache


async def refresh():
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        result = await session.execute(
            select(ReviewCache).where(ReviewCache.expires_at < now)
        )
        expired = result.scalars().all()

    print(f"Found {len(expired)} expired review cache entries to refresh")
    print("Re-fetching reviews would require API calls — run the main search to refresh on demand")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(refresh())
