import asyncio

import httpx

from app.config import settings


async def search_restaurants(lat: float, lng: float) -> list[dict]:
    yelp_task = _search_yelp(lat, lng)
    google_task = _search_google_places(lat, lng)

    yelp_results, google_results = await asyncio.gather(yelp_task, google_task)

    merged = _deduplicate(yelp_results + google_results)
    return merged


async def _search_yelp(lat: float, lng: float) -> list[dict]:
    url = "https://api.yelp.com/v3/businesses/search"
    headers = {"Authorization": f"Bearer {settings.yelp_api_key}"}
    params = {
        "latitude": lat,
        "longitude": lng,
        "radius": 8000,
        "categories": "food,restaurants",
        "limit": 50,
        "sort_by": "best_match",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            return []
        data = resp.json()

    results = []
    for biz in data.get("businesses", []):
        location = biz.get("location", {})
        address_parts = [
            location.get("address1", ""),
            location.get("city", ""),
            location.get("state", ""),
        ]
        results.append(
            {
                "id": f"yelp_{biz['id']}",
                "yelp_id": biz["id"],
                "name": biz["name"],
                "address": ", ".join(p for p in address_parts if p),
                "lat": biz["coordinates"]["latitude"],
                "lng": biz["coordinates"]["longitude"],
                "rating": biz.get("rating", 0),
                "review_count": biz.get("review_count", 0),
                "photo_url": biz.get("image_url"),
                "cuisine_tags": [
                    c["alias"] for c in biz.get("categories", [])
                ],
                "price_level": biz.get("price"),
            }
        )

    return results


async def _search_google_places(lat: float, lng: float) -> list[dict]:
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": 8000,
        "type": "restaurant",
        "key": settings.google_maps_api_key,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            return []
        data = resp.json()

    results = []
    for place in data.get("results", []):
        geo = place.get("geometry", {}).get("location", {})
        photo_url = None
        if place.get("photos"):
            photo_ref = place["photos"][0].get("photo_reference")
            if photo_ref:
                photo_url = (
                    f"https://maps.googleapis.com/maps/api/place/photo"
                    f"?maxwidth=400&photo_reference={photo_ref}"
                    f"&key={settings.google_maps_api_key}"
                )

        results.append(
            {
                "id": f"google_{place['place_id']}",
                "google_place_id": place["place_id"],
                "name": place["name"],
                "address": place.get("vicinity", ""),
                "lat": geo.get("lat", 0),
                "lng": geo.get("lng", 0),
                "rating": place.get("rating", 0),
                "review_count": place.get("user_ratings_total", 0),
                "photo_url": photo_url,
                "cuisine_tags": place.get("types", []),
                "price_level": _google_price_to_string(
                    place.get("price_level")
                ),
            }
        )

    return results


def _google_price_to_string(level: int | None) -> str | None:
    mapping = {0: "$", 1: "$", 2: "$$", 3: "$$$", 4: "$$$$"}
    return mapping.get(level)


def _deduplicate(restaurants: list[dict]) -> list[dict]:
    seen = {}
    for r in restaurants:
        name_key = r["name"].lower().strip()
        if name_key not in seen:
            seen[name_key] = r
        else:
            existing = seen[name_key]
            if r.get("review_count", 0) > existing.get("review_count", 0):
                seen[name_key] = r
    return list(seen.values())
