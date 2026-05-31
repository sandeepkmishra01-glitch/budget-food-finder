import httpx

from app.config import settings


async def geocode_address(address: str) -> tuple[float, float] | None:
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": settings.google_maps_api_key,
        "components": "country:US",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        data = resp.json()

    if data.get("status") != "OK" or not data.get("results"):
        return None

    location = data["results"][0]["geometry"]["location"]
    return location["lat"], location["lng"]
