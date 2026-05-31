import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.search_cache import SearchCache
from app.schemas.search import SearchRequest, SearchResponse, SearchMeta
from app.services.geocoding import geocode_address
from app.services.restaurant_search import search_restaurants
from app.services.distance import get_travel_times
from app.services.reviews import fetch_reviews_for_restaurants
from app.services.dish_extractor import extract_dishes_for_restaurants
from app.services.ranking import rank_results

router = APIRouter()

MIN_RESULTS = 5
PRIMARY_TIME_LIMIT = 20
EXPANDED_TIME_LIMIT = 45
MIN_REVIEW_COUNT = 10


def make_cache_key(address: str, mode: str) -> str:
    normalized = address.strip().lower()
    raw = f"{normalized}:{mode}"
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest, db: AsyncSession = Depends(get_db)):
    cache_key = make_cache_key(request.address, request.travel_mode)

    cached = await db.execute(
        select(SearchCache).where(
            SearchCache.cache_key == cache_key,
            SearchCache.expires_at > datetime.now(timezone.utc),
        )
    )
    cached_result = cached.scalar_one_or_none()
    if cached_result:
        return SearchResponse(**cached_result.results_json)

    coords = await geocode_address(request.address)
    if not coords:
        return SearchResponse(
            results=[],
            meta=SearchMeta(
                total_count=0,
                travel_mode=request.travel_mode,
            ),
        )

    lat, lng = coords
    restaurants = await search_restaurants(lat, lng)

    travel_times = await get_travel_times(
        lat, lng, restaurants, request.travel_mode
    )

    transit_unavailable = False
    if request.travel_mode == "transit" and not travel_times:
        transit_unavailable = True

    results = []
    for restaurant in restaurants:
        time_min = travel_times.get(restaurant["id"])
        if time_min is None:
            continue
        if time_min <= PRIMARY_TIME_LIMIT:
            restaurant["travel_time_minutes"] = time_min
            results.append(restaurant)

    radius_expanded = False
    if len(results) < MIN_RESULTS and not transit_unavailable:
        radius_expanded = True
        for restaurant in restaurants:
            time_min = travel_times.get(restaurant["id"])
            if time_min is None:
                continue
            if PRIMARY_TIME_LIMIT < time_min <= EXPANDED_TIME_LIMIT:
                restaurant["travel_time_minutes"] = time_min
                results.append(restaurant)

    results = [r for r in results if r.get("review_count", 0) >= MIN_REVIEW_COUNT]

    results = await fetch_reviews_for_restaurants(results, db)
    results = extract_dishes_for_restaurants(results)
    results = rank_results(results)

    for r in results:
        r["travel_mode"] = request.travel_mode

    response = SearchResponse(
        results=results,
        meta=SearchMeta(
            total_count=len(results),
            radius_expanded=radius_expanded,
            travel_mode=request.travel_mode,
            transit_unavailable=transit_unavailable,
        ),
    )

    cache_entry = SearchCache(
        cache_key=cache_key,
        query_address=request.address,
        normalized_address=request.address.strip().lower(),
        travel_mode=request.travel_mode,
        lat=lat,
        lng=lng,
        results_json=response.model_dump(),
        result_count=len(results),
        radius_expanded=radius_expanded,
        cached_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc)
        + timedelta(seconds=settings.cache_ttl_search),
    )
    db.add(cache_entry)
    await db.commit()

    return response
