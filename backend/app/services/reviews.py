import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.review_cache import ReviewCache


async def fetch_reviews_for_restaurants(
    restaurants: list[dict], db: AsyncSession
) -> list[dict]:
    tasks = [_fetch_reviews_single(r, db) for r in restaurants]
    results = await asyncio.gather(*tasks)
    return results


async def _fetch_reviews_single(
    restaurant: dict, db: AsyncSession
) -> dict:
    restaurant_id = restaurant["id"]

    cached = await db.execute(
        select(ReviewCache).where(
            ReviewCache.restaurant_id == hash(restaurant_id) % 2147483647,
            ReviewCache.expires_at > datetime.now(timezone.utc),
        )
    )
    cached_review = cached.scalar_one_or_none()

    if cached_review:
        restaurant["snippets"] = [
            {"text": s[:120], "source": cached_review.source}
            for s in (cached_review.snippets or [])[:2]
        ]
        restaurant["dish_mentions"] = cached_review.dish_mentions or []
        return restaurant

    snippets = []
    raw_reviews = []

    yelp_id = restaurant.get("yelp_id")
    if yelp_id:
        yelp_reviews = await _fetch_yelp_reviews(yelp_id)
        for review in yelp_reviews:
            text = review.get("text", "")
            raw_reviews.append(text)
            if len(snippets) < 2:
                snippets.append({"text": text[:120], "source": "yelp"})

    google_place_id = restaurant.get("google_place_id")
    if google_place_id:
        google_reviews = await _fetch_google_reviews(google_place_id)
        for review in google_reviews:
            text = review.get("text", "")
            raw_reviews.append(text)
            if len(snippets) < 2:
                snippets.append({"text": text[:120], "source": "google"})

    restaurant["snippets"] = snippets
    restaurant["raw_reviews"] = raw_reviews
    return restaurant


async def _fetch_yelp_reviews(yelp_id: str) -> list[dict]:
    url = f"https://api.yelp.com/v3/businesses/{yelp_id}/reviews"
    headers = {"Authorization": f"Bearer {settings.yelp_api_key}"}
    params = {"limit": 3, "sort_by": "yelp_sort"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            return []
        data = resp.json()

    return data.get("reviews", [])


async def _fetch_google_reviews(place_id: str) -> list[dict]:
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "reviews",
        "key": settings.google_maps_api_key,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            return []
        data = resp.json()

    result = data.get("result", {})
    return result.get("reviews", [])
