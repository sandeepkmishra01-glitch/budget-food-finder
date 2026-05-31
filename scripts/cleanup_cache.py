"""Delete expired cache entries from the database."""
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.models.search_cache import SearchCache
from app.models.review_cache import ReviewCache
from app.database import Base


async def cleanup():
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        result_search = await session.execute(
            delete(SearchCache).where(SearchCache.expires_at < now)
        )
        result_review = await session.execute(
            delete(ReviewCache).where(ReviewCache.expires_at < now)
        )
        await session.commit()

    print(f"Deleted {result_search.rowcount} expired search cache entries")
    print(f"Deleted {result_review.rowcount} expired review cache entries")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(cleanup())
