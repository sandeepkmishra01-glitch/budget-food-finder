import os
import asyncio
import re
from contextlib import asynccontextmanager
from typing import Literal
from pathlib import Path
from collections import Counter

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx

# ── Config ──────────────────────────────────────────────────────────────────

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# ── Schemas ─────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    address: str
    travel_mode: Literal["walking", "transit", "driving"] = "driving"


class ReviewSnippet(BaseModel):
    text: str
    source: str = "google"


class BudgetItem(BaseModel):
    name: str
    price_estimate: int


class RestaurantResult(BaseModel):
    id: str
    name: str
    address: str
    lat: float
    lng: float
    photo_url: str | None = None
    google_place_id: str | None = None
    cuisine_tags: list[str] = []
    travel_time_minutes: int
    travel_mode: str
    rating: float
    review_count: int
    price_level: str | None = None
    snippets: list[ReviewSnippet] = []
    dish_mentions: list[str] = []
    budget_items: list[BudgetItem] = []
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
    return await _search_google_places(lat, lng)



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


async def fetch_reviews_for_restaurants(restaurants: list[dict]) -> list[dict]:
    tasks = [_fetch_reviews_single(r) for r in restaurants]
    return await asyncio.gather(*tasks)


def _is_food_review(text: str) -> bool:
    text_lower = text.lower()
    return bool(DISH_PATTERN.search(text_lower)) or any(
        w in text_lower for w in ("delicious", "tasty", "flavor", "portion", "menu", "order", "dish", "meal", "cook", "fresh", "yummy")
    )


async def _fetch_reviews_single(restaurant: dict) -> dict:
    snippets = []
    raw_reviews = []

    google_place_id = restaurant.get("google_place_id")
    if google_place_id:
        for review in await _fetch_google_reviews(google_place_id):
            t = review.get("text", "")
            if not _is_food_review(t):
                continue
            raw_reviews.append(t)
            if len(snippets) < 2:
                snippets.append({"text": t[:120], "source": "google"})

    restaurant["snippets"] = snippets
    restaurant["raw_reviews"] = raw_reviews
    return restaurant


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


PRICE_RANGES = {
    "$": (4, 8),
    "$$": (8, 14),
    "$$$": (14, 25),
    "$$$$": (25, 50),
}


def extract_dishes_for_restaurants(restaurants: list[dict]) -> list[dict]:
    for r in restaurants:
        raw = r.pop("raw_reviews", [])
        dishes = extract_dishes(raw) if raw else r.get("dish_mentions", [])
        price_level = r.get("price_level") or "$$"
        low, high = PRICE_RANGES.get(price_level, (8, 14))
        r["dish_mentions"] = dishes
        r["budget_items"] = [
            {"name": d, "price_estimate": low + (i * (high - low)) // max(len(dishes), 1)}
            for i, d in enumerate(dishes)
        ]
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
async def health_check():
    return {"status": "ok"}


@app.get("/api/config")
async def get_config():
    return {"google_maps_api_key": GOOGLE_MAPS_API_KEY}


@app.get("/api/cuisines")
async def get_cuisines():
    return CUISINES


@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest):
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
    results = await fetch_reviews_for_restaurants(results)
    results = extract_dishes_for_restaurants(results)
    results = rank_results(results)

    for r in results:
        r["travel_mode"] = request.travel_mode

    return SearchResponse(
        results=results,
        meta=SearchMeta(
            total_count=len(results),
            radius_expanded=radius_expanded,
            travel_mode=request.travel_mode,
            transit_unavailable=transit_unavailable,
        ),
    )


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
