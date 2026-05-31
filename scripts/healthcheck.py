"""Verify system health: backend, database, and API keys."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

import httpx
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def check_database():
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    try:
        engine = create_async_engine(database_url)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True, "Connected"
    except Exception as e:
        return False, str(e)


async def check_yelp_api():
    api_key = os.environ.get("YELP_API_KEY", "")
    if not api_key:
        return False, "YELP_API_KEY not set"

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.yelp.com/v3/businesses/search",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"latitude": 40.7128, "longitude": -74.0060, "limit": 1},
        )
    if resp.status_code == 200:
        return True, "Valid"
    return False, f"Status {resp.status_code}"


async def check_google_api():
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return False, "GOOGLE_MAPS_API_KEY not set"

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": "New York, NY", "key": api_key},
        )
    data = resp.json()
    if data.get("status") == "OK":
        return True, "Valid"
    return False, f"Status: {data.get('status')}"


async def main():
    checks = {
        "Database": check_database(),
        "Yelp API": check_yelp_api(),
        "Google Maps API": check_google_api(),
    }

    print("=== Budget Food Finder Health Check ===\n")
    all_pass = True

    for name, coro in checks.items():
        ok, msg = await coro
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {name}: {msg}")

    print()
    if all_pass:
        print("All checks passed!")
    else:
        print("Some checks failed. Fix issues above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
