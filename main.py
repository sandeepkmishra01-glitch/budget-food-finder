import os
import hashlib
import asyncio
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal
from pathlib import Path
from collections import Counter

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Numeric, ForeignKey, text, select, ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
import httpx

# ── Config ──────────────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+asyncpg://localhost/food_finder")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
YELP_API_KEY = os.environ.get("YELP_API_KEY", "")
CACHE_TTL_SEARCH = int(os.environ.get("CACHE_TTL_SEARCH", "3600"))
CACHE_TTL_REVIEWS = int(os.environ.get("CACHE_TTL_REVIEWS", "86400"))

# ── Database ────────────────────────────────────────────────────────────────

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


# ── Models ──────────────────────────────────────────────────────────────────

class Restaurant(Base):
    __tablename__ = "restaurants"
    id = Column(Integer, primary_key=True)
    yelp_id = Column(String, unique=True, nullable=True, index=True)
    google_place_id = Column(String, unique=True, nullable=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String)
    lat = Column(Float)
    lng = Column(Float)
    cuisine_tags = Column(ARRAY(String))
    price_level = Column(String)
    photo_url = Column(String)


class MenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), index=True)
    item_name = Column(String, nullable=False)
    price = Column(Numeric(5, 2))
    photo_url = Column(String)
    source = Column(String)


class SearchCache(Base):
    __tablename__ = "search_cache"
    id = Column(Integer, primary_key=True)
    cache_key = Column(String, unique=True, index=True)
    query_address = Column(String, nullable=False)
    normalized_address = Column(String)
    travel_mode = Column(String, nullable=False)
    lat = Column(Float)
    lng = Column(Float)
    results_json = Column(JSONB, nullable=False)
    result_count = Column(Integer)
    radius_expanded = Column(Boolean, default=False)
    cached_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime)


class ReviewCache(Base):
    __tablename__ = "review_cache"
    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), index=True)
    source = Column(String, nullable=False)
    rating = Column(Numeric(2, 1))
    review_count = Column(Integer)
    snippets = Column(ARRAY(String))
    dish_mentions = Column(ARRAY(String))
    raw_reviews = Column(JSONB)
    cached_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime)


# ── Schemas ─────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    address: str
    travel_mode: Literal["walking", "transit", "driving"] = "driving"


class ReviewSnippet(BaseModel):
    text: str
    source: Literal["yelp", "google"]


class RestaurantResult(BaseModel):
    id: str
    name: str
    address: str
    lat: float
    lng: float
    photo_url: str | None = None
    cuisine_tags: list[str] = []
    travel_time_minutes: int
    travel_mode: str
    rating: float
    review_count: int
    price_level: str | None = None
    snippets: list[ReviewSnippet] = []
    dish_mentions: list[str] = []
    score: float = 0.0


class SearchMeta(BaseModel):
    total_count: int
    radius_expanded: bool = False
    travel_mode: str
    transit_unavailable: bool = False


class SearchResponse(BaseModel):
    results: list[RestaurantResult]
    meta: SearchMeta


# ── Services ────────────────────────────────────────────────────────────────

async def geocode_address(address: str) -> tuple[float, float] | None:
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_MAPS_API_KEY, "components": "country:US"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        return None
    location = data["results"][0]["geometry"]["location"]
    return location["lat"], location["lng"]


async def search_restaurants(lat: float, lng: float) -> list[dict]:
    yelp_results, google_results = await asyncio.gather(
        _search_yelp(lat, lng), _search_google_places(lat, lng)
    )
    return _deduplicate(yelp_results + google_results)


async def _search_yelp(lat: float, lng: float) -> list[dict]:
    url = "https://api.yelp.com/v3/businesses/search"
    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
    params = {
        "latitude": lat, "longitude": lng, "radius": 8000,
        "categories": "food,restaurants", "limit": 50, "sort_by": "best_match",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            return []
        data = resp.json()
    results = []
    for biz in data.get("businesses", []):
        loc = biz.get("location", {})
        addr_parts = [loc.get("address1", ""), loc.get("city", ""), loc.get("state", "")]
        results.append({
            "id": f"yelp_{biz['id']}", "yelp_id": biz["id"], "name": biz["name"],
            "address": ", ".join(p for p in addr_parts if p),
            "lat": biz["coordinates"]["latitude"], "lng": biz["coordinates"]["longitude"],
            "rating": biz.get("rating", 0), "review_count": biz.get("review_count", 0),
            "photo_url": biz.get("image_url"),
            "cuisine_tags": [c["alias"] for c in biz.get("categories", [])],
            "price_level": biz.get("price"),
        })
    return results


async def _search_google_places(lat: float, lng: float) -> list[dict]:
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {"location": f"{lat},{lng}", "radius": 8000, "type": "restaurant", "key": GOOGLE_MAPS_API_KEY}
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
                photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference={photo_ref}&key={GOOGLE_MAPS_API_KEY}"
        price_map = {0: "$", 1: "$", 2: "$$", 3: "$$$", 4: "$$$$"}
        results.append({
            "id": f"google_{place['place_id']}", "google_place_id": place["place_id"],
            "name": place["name"], "address": place.get("vicinity", ""),
            "lat": geo.get("lat", 0), "lng": geo.get("lng", 0),
            "rating": place.get("rating", 0), "review_count": place.get("user_ratings_total", 0),
            "photo_url": photo_url, "cuisine_tags": place.get("types", []),
            "price_level": price_map.get(place.get("price_level")),
        })
    return results


def _deduplicate(restaurants: list[dict]) -> list[dict]:
    seen = {}
    for r in restaurants:
        key = r["name"].lower().strip()
        if key not in seen or r.get("review_count", 0) > seen[key].get("review_count", 0):
            seen[key] = r
    return list(seen.values())


BATCH_SIZE = 25


async def get_travel_times(origin_lat: float, origin_lng: float, restaurants: list[dict], mode: str) -> dict[str, int]:
    if not restaurants:
        return {}
    origin = f"{origin_lat},{origin_lng}"
    batches = [restaurants[i:i + BATCH_SIZE] for i in range(0, len(restaurants), BATCH_SIZE)]
    results = {}
    async with httpx.AsyncClient() as client:
        batch_results = await asyncio.gather(*[_fetch_travel_batch(client, origin, b, mode) for b in batches])
    for br in batch_results:
        results.update(br)
    return results


async def _fetch_travel_batch(client: httpx.AsyncClient, origin: str, batch: list[dict], mode: str) -> dict[str, int]:
    destinations = "|".join(f"{r['lat']},{r['lng']}" for r in batch)
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {"origins": origin, "destinations": destinations, "mode": mode, "key": GOOGLE_MAPS_API_KEY}
    resp = await client.get(url, params=params)
    data = resp.json()
    results = {}
    elements = data.get("rows", [{}])[0].get("elements", [])
    for i, element in enumerate(elements):
        if i >= len(batch):
            break
        if element.get("status") == "OK":
            results[batch[i]["id"]] = element["duration"]["value"] // 60
    return results


async def fetch_reviews_for_restaurants(restaurants: list[dict], db: AsyncSession) -> list[dict]:
    tasks = [_fetch_reviews_single(r, db) for r in restaurants]
    return await asyncio.gather(*tasks)


async def _fetch_reviews_single(restaurant: dict, db: AsyncSession) -> dict:
    restaurant_id = restaurant["id"]
    cached = await db.execute(
        select(ReviewCache).where(
            ReviewCache.restaurant_id == hash(restaurant_id) % 2147483647,
            ReviewCache.expires_at > datetime.now(timezone.utc),
        )
    )
    cached_review = cached.scalar_one_or_none()
    if cached_review:
        restaurant["snippets"] = [{"text": s[:120], "source": cached_review.source} for s in (cached_review.snippets or [])[:2]]
        restaurant["dish_mentions"] = cached_review.dish_mentions or []
        return restaurant

    snippets = []
    raw_reviews = []

    yelp_id = restaurant.get("yelp_id")
    if yelp_id:
        for review in await _fetch_yelp_reviews(yelp_id):
            t = review.get("text", "")
            raw_reviews.append(t)
            if len(snippets) < 2:
                snippets.append({"text": t[:120], "source": "yelp"})

    google_place_id = restaurant.get("google_place_id")
    if google_place_id:
        for review in await _fetch_google_reviews(google_place_id):
            t = review.get("text", "")
            raw_reviews.append(t)
            if len(snippets) < 2:
                snippets.append({"text": t[:120], "source": "google"})

    restaurant["snippets"] = snippets
    restaurant["raw_reviews"] = raw_reviews
    return restaurant


async def _fetch_yelp_reviews(yelp_id: str) -> list[dict]:
    url = f"https://api.yelp.com/v3/businesses/{yelp_id}/reviews"
    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params={"limit": 3, "sort_by": "yelp_sort"})
        if resp.status_code != 200:
            return []
        return resp.json().get("reviews", [])


async def _fetch_google_reviews(place_id: str) -> list[dict]:
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {"place_id": place_id, "fields": "reviews", "key": GOOGLE_MAPS_API_KEY}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            return []
        return resp.json().get("result", {}).get("reviews", [])


# ── Dish extractor ──────────────────────────────────────────────────────────

FOOD_NOUNS = {
    "taco", "tacos", "burrito", "burritos", "bowl", "bowls", "rice", "noodles",
    "pizza", "burger", "burgers", "sandwich", "sandwiches", "wings", "fries",
    "soup", "salad", "sushi", "roll", "rolls", "ramen", "pho", "curry",
    "dumpling", "dumplings", "birria", "carnitas", "carne asada", "al pastor",
    "quesadilla", "nachos", "tamale", "tamales", "torta", "elote", "pozole",
    "chilaquiles", "mole", "pad thai", "lo mein", "fried rice", "bibimbap",
    "bulgogi", "shawarma", "falafel", "hummus", "gyro", "kebab", "tikka",
    "naan", "biryani", "samosa", "paneer", "tandoori", "masala", "dosa",
    "pasta", "lasagna", "ravioli", "risotto", "calzone", "penne", "spaghetti",
    "carbonara", "alfredo", "marinara", "bolognese", "pesto", "steak", "ribs",
    "brisket", "pulled pork", "bbq", "chicken", "shrimp", "salmon", "fish",
    "poke", "ceviche", "calamari", "wonton", "bao", "banh mi", "spring roll",
    "tempura", "teriyaki", "katsu", "udon", "soba", "miso", "yakitori",
    "waffle", "pancake", "crepe", "croissant", "donut", "bagel", "pie", "cake",
    "cookie", "brownie", "ice cream", "gelato", "smoothie", "acai", "matcha",
    "coffee", "latte", "espresso", "boba", "bubble tea", "hot dog", "pretzel",
    "mac and cheese", "grilled cheese", "philly cheesesteak", "wrap", "sub",
}

FOOD_ADJECTIVES = {
    "spicy", "crispy", "grilled", "fried", "smoked", "roasted", "bbq",
    "buffalo", "teriyaki", "garlic", "honey", "lemon", "sesame", "truffle",
    "loaded", "stuffed", "double", "classic", "signature", "house", "homemade",
    "fresh", "glazed", "braised", "seared", "blackened", "cajun", "creamy",
    "cheesy", "hot", "sweet", "sour", "tangy", "savory", "zesty",
}

_adj_pattern = "|".join(re.escape(a) for a in sorted(FOOD_ADJECTIVES, key=len, reverse=True))
_noun_pattern = "|".join(re.escape(n) for n in sorted(FOOD_NOUNS, key=len, reverse=True))
DISH_PATTERN = re.compile(rf"\b(?:(?:{_adj_pattern})\s+)?(?:{_noun_pattern})(?:\s+(?:{_noun_pattern}))?", re.IGNORECASE)


def extract_dishes(reviews: list[str], min_mentions: int = 2) -> list[str]:
    if not reviews:
        return []
    candidates = Counter()
    for review in reviews:
        found = set()
        for match in DISH_PATTERN.finditer(review.lower()):
            dish = re.sub(r"\s+", " ", match.group().strip())
            if len(dish) > 2:
                found.add(dish)
        candidates.update(found)
    frequent = {d: c for d, c in candidates.items() if c >= min_mentions}
    return [d for d, _ in sorted(frequent.items(), key=lambda x: x[1], reverse=True)[:5]]


def extract_dishes_for_restaurants(restaurants: list[dict]) -> list[dict]:
    for r in restaurants:
        raw = r.pop("raw_reviews", [])
        if raw:
            r["dish_mentions"] = extract_dishes(raw)
        elif "dish_mentions" not in r:
            r["dish_mentions"] = []
    return restaurants


# ── Ranking ─────────────────────────────────────────────────────────────────

def rank_results(restaurants: list[dict]) -> list[dict]:
    for r in restaurants:
        rating_score = (r.get("rating", 0) / 5.0) * 0.40
        review_score = (min(r.get("review_count", 0), 1000) / 1000) * 0.30
        price_map = {"$": 1.0, "$$": 0.6, "$$$": 0.3, "$$$$": 0.1}
        price_score = price_map.get(r.get("price_level") or "$$", 0.5) * 0.20
        travel_score = ((45 - r.get("travel_time_minutes", 45)) / 45) * 0.10
        r["score"] = rating_score + review_score + price_score + travel_score
    restaurants.sort(key=lambda r: r["score"], reverse=True)
    return restaurants


# ── Cuisines ────────────────────────────────────────────────────────────────

CUISINES = [
    {"key": "all", "label": "All", "emoji": "\U0001f371"},
    {"key": "mexican", "label": "Mexican", "emoji": "\U0001f32e"},
    {"key": "pizza", "label": "Pizza", "emoji": "\U0001f355"},
    {"key": "burgers", "label": "Burgers", "emoji": "\U0001f354"},
    {"key": "asian", "label": "Asian", "emoji": "\U0001f35c"},
    {"key": "healthy", "label": "Healthy", "emoji": "\U0001f957"},
    {"key": "chicken", "label": "Chicken", "emoji": "\U0001f357"},
    {"key": "wraps", "label": "Wraps", "emoji": "\U0001f32f"},
    {"key": "sandwiches", "label": "Sandwiches", "emoji": "\U0001f96a"},
    {"key": "sushi", "label": "Sushi", "emoji": "\U0001f363"},
    {"key": "indian", "label": "Indian", "emoji": "\U0001f35b"},
    {"key": "mediterranean", "label": "Mediterranean", "emoji": "\U0001f959"},
    {"key": "italian", "label": "Italian", "emoji": "\U0001f35d"},
    {"key": "cafe", "label": "Café/Bakery", "emoji": "☕"},
    {"key": "bbq", "label": "BBQ", "emoji": "\U0001f336️"},
]

# ── App ─────────────────────────────────────────────────────────────────────

MIN_RESULTS = 5
PRIMARY_TIME_LIMIT = 20
EXPANDED_TIME_LIMIT = 45
MIN_REVIEW_COUNT = 10


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Budget Food Finder", lifespan=lifespan)


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception:
        return {"status": "degraded", "db": "disconnected"}


@app.get("/api/cuisines")
async def get_cuisines():
    return CUISINES


@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest, db: AsyncSession = Depends(get_db)):
    normalized = request.address.strip().lower()
    cache_key = hashlib.sha256(f"{normalized}:{request.travel_mode}".encode()).hexdigest()

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
        return SearchResponse(results=[], meta=SearchMeta(total_count=0, travel_mode=request.travel_mode))

    lat, lng = coords
    restaurants = await search_restaurants(lat, lng)
    travel_times = await get_travel_times(lat, lng, restaurants, request.travel_mode)

    transit_unavailable = request.travel_mode == "transit" and not travel_times

    results = []
    for r in restaurants:
        time_min = travel_times.get(r["id"])
        if time_min is not None and time_min <= PRIMARY_TIME_LIMIT:
            r["travel_time_minutes"] = time_min
            results.append(r)

    radius_expanded = False
    if len(results) < MIN_RESULTS and not transit_unavailable:
        radius_expanded = True
        for r in restaurants:
            time_min = travel_times.get(r["id"])
            if time_min is not None and PRIMARY_TIME_LIMIT < time_min <= EXPANDED_TIME_LIMIT:
                r["travel_time_minutes"] = time_min
                results.append(r)

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
        cache_key=cache_key, query_address=request.address,
        normalized_address=normalized, travel_mode=request.travel_mode,
        lat=lat, lng=lng, results_json=response.model_dump(),
        result_count=len(results), radius_expanded=radius_expanded,
        cached_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=CACHE_TTL_SEARCH),
    )
    db.add(cache_entry)
    await db.commit()

    return response


# ── Static frontend ─────────────────────────────────────────────────────────

STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        file_path = STATIC_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
