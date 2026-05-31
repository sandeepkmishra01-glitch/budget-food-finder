import asyncio

import httpx

from app.config import settings

BATCH_SIZE = 25


async def get_travel_times(
    origin_lat: float,
    origin_lng: float,
    restaurants: list[dict],
    mode: str,
) -> dict[str, int]:
    if not restaurants:
        return {}

    origin = f"{origin_lat},{origin_lng}"
    batches = [
        restaurants[i : i + BATCH_SIZE]
        for i in range(0, len(restaurants), BATCH_SIZE)
    ]

    results = {}

    async with httpx.AsyncClient() as client:
        tasks = [
            _fetch_batch(client, origin, batch, mode) for batch in batches
        ]
        batch_results = await asyncio.gather(*tasks)

    for batch_result in batch_results:
        results.update(batch_result)

    return results


async def _fetch_batch(
    client: httpx.AsyncClient,
    origin: str,
    batch: list[dict],
    mode: str,
) -> dict[str, int]:
    destinations = "|".join(
        f"{r['lat']},{r['lng']}" for r in batch
    )

    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": origin,
        "destinations": destinations,
        "mode": mode,
        "key": settings.google_maps_api_key,
    }

    resp = await client.get(url, params=params)
    data = resp.json()

    results = {}
    elements = data.get("rows", [{}])[0].get("elements", [])

    for i, element in enumerate(elements):
        if i >= len(batch):
            break
        restaurant_id = batch[i]["id"]
        if element.get("status") == "OK":
            duration_seconds = element["duration"]["value"]
            results[restaurant_id] = duration_seconds // 60

    return results
