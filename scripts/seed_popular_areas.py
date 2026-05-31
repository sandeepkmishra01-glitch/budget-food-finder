"""Pre-populate search cache for popular metro areas."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

import httpx

POPULAR_ADDRESSES = [
    "Times Square, New York, NY",
    "Union Square, New York, NY",
    "Williamsburg, Brooklyn, NY",
    "Hollywood Blvd, Los Angeles, CA",
    "Santa Monica, CA",
    "Downtown Los Angeles, CA",
    "The Loop, Chicago, IL",
    "Wicker Park, Chicago, IL",
    "Mission District, San Francisco, CA",
    "Downtown Austin, TX",
]

MODES = ["driving", "walking"]


async def seed():
    backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")

    print(f"Seeding cache via {backend_url}/api/search\n")

    async with httpx.AsyncClient(timeout=60.0) as client:
        for address in POPULAR_ADDRESSES:
            for mode in MODES:
                try:
                    resp = await client.post(
                        f"{backend_url}/api/search",
                        json={"address": address, "travel_mode": mode},
                    )
                    data = resp.json()
                    count = data.get("meta", {}).get("total_count", 0)
                    print(f"  [{mode:8}] {address}: {count} results")
                except Exception as e:
                    print(f"  [ERROR] {address} ({mode}): {e}")

                await asyncio.sleep(1)

    print("\nSeeding complete!")


if __name__ == "__main__":
    asyncio.run(seed())
