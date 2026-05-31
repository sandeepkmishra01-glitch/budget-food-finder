import os
import asyncio
import re
from contextlib import asynccontextmanager
from pathlib import Path
from collections import Counter

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx

# ── Config ──────────────────────────────────────────────────────────────────

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
FOURSQUARE_API_KEY = os.environ.get("FOURSQUARE_API_KEY", "")

# ── Schemas ─────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    address: str
    open_now: bool = True


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
    website: str | None = None
    cuisine_tags: list[str] = []
    rating: float
    review_count: int
    price_level: str | None = None
    dish_mentions: list[str] = []
    budget_items: list[BudgetItem] = []
    score: float = 0.0


class SearchMeta(BaseModel):
    total_count: int


class SearchResponse(BaseModel):
    results: list[RestaurantResult]
    meta: SearchMeta


# ── Services ────────────────────────────────────────────────────────────────

EXCLUDED_TYPES = {"lodging", "hotel", "motel", "inn", "resort", "spa", "gym", "car_dealer", "car_repair", "gas_station", "parking"}
EXCLUDED_NAME_WORDS = {"hotel", "inn", "motel", "resort", "suites", "lodge", "hostel"}


def _is_restaurant(place: dict) -> bool:
    types = set(place.get("types", []))
    if types & EXCLUDED_TYPES:
        return False
    name_lower = place.get("name", "").lower()
    if any(w in name_lower for w in EXCLUDED_NAME_WORDS):
        return False
    return True


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


async def search_restaurants(lat: float, lng: float, open_now: bool = True) -> list[dict]:
    search_types = ["restaurant", "cafe", "meal_takeaway", "bakery"]
    tasks = [_search_by_type(lat, lng, t, open_now) for t in search_types]
    if FOURSQUARE_API_KEY:
        tasks.append(_search_foursquare(lat, lng, open_now))
    all_results = await asyncio.gather(*tasks)
    combined = []
    for batch in all_results:
        combined.extend(batch)
    # Deduplicate by name (cross-source)
    seen = {}
    for r in combined:
        key = r["name"].lower().strip()
        if key not in seen or r.get("review_count", 0) > seen[key].get("review_count", 0):
            seen[key] = r
    return list(seen.values())


async def _search_by_type(lat: float, lng: float, place_type: str, open_now: bool = True) -> list[dict]:
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {"location": f"{lat},{lng}", "radius": 3000, "type": place_type, "key": GOOGLE_MAPS_API_KEY}
    if open_now:
        params["opennow"] = "true"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            return []
        data = resp.json()
    results = []
    for place in data.get("results", []):
        if not _is_restaurant(place):
            continue
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


async def _search_foursquare(lat: float, lng: float, open_now: bool = True) -> list[dict]:
    url = "https://api.foursquare.com/v3/places/search"
    headers = {"Authorization": FOURSQUARE_API_KEY, "Accept": "application/json"}
    params = {
        "ll": f"{lat},{lng}",
        "radius": 3000,
        "categories": "13065,13032,13034,13040,13046,13048,13059,13064,13067",
        "limit": 50,
        "fields": "fsq_id,name,location,rating,price,photos,website,categories",
    }
    if open_now:
        params["open_now"] = "true"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            return []
        data = resp.json()
    results = []
    for place in data.get("results", []):
        name = place.get("name", "")
        name_lower = name.lower()
        if any(w in name_lower for w in EXCLUDED_NAME_WORDS):
            continue
        location = place.get("location", {})
        lat_p = location.get("latitude", 0)
        lng_p = location.get("longitude", 0)
        address = location.get("formatted_address", location.get("address", ""))
        fsq_price = place.get("price")
        price_map = {1: "$", 2: "$$", 3: "$$$", 4: "$$$$"}
        photo_url = None
        photos = place.get("photos", [])
        if photos:
            p = photos[0]
            photo_url = f"{p.get('prefix', '')}400x300{p.get('suffix', '')}"
        cuisine_tags = [c.get("short_name", "").lower() for c in place.get("categories", [])]
        results.append({
            "id": f"fsq_{place.get('fsq_id', '')}",
            "google_place_id": None,
            "name": name,
            "address": address,
            "lat": lat_p,
            "lng": lng_p,
            "rating": (place.get("rating", 0) / 2),
            "review_count": 0,
            "photo_url": photo_url,
            "cuisine_tags": cuisine_tags,
            "price_level": price_map.get(fsq_price),
            "website": place.get("website"),
        })
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
    raw_reviews = []

    google_place_id = restaurant.get("google_place_id")
    if google_place_id:
        details = await _fetch_place_details(google_place_id)
        restaurant["website"] = details.get("website")
        for review in details.get("reviews", []):
            t = review.get("text", "")
            if not _is_food_review(t):
                continue
            raw_reviews.append(t)

    restaurant["raw_reviews"] = raw_reviews
    return restaurant


async def _fetch_place_details(place_id: str) -> dict:
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {"place_id": place_id, "fields": "reviews,website", "key": GOOGLE_MAPS_API_KEY}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            return {}
        return resp.json().get("result", {})


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
        rating_score = (r.get("rating", 0) / 5.0) * 0.50
        review_score = (min(r.get("review_count", 0), 1000) / 1000) * 0.25
        price_map = {"$": 1.0, "$$": 0.6, "$$$": 0.3, "$$$$": 0.1}
        price_score = price_map.get(r.get("price_level") or "$$", 0.5) * 0.25
        r["score"] = rating_score + review_score + price_score
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

MIN_REVIEW_COUNT = 5


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


@app.post("/api/search")
async def search(request: SearchRequest):
    coords = await geocode_address(request.address)
    if not coords:
        return {"results": [], "meta": {"total_count": 0}}

    lat, lng = coords
    restaurants = await search_restaurants(lat, lng, open_now=request.open_now)

    results = [r for r in restaurants if r.get("review_count", 0) >= MIN_REVIEW_COUNT]
    results = await fetch_reviews_for_restaurants(results)
    results = extract_dishes_for_restaurants(results)
    results = rank_results(results)

    return {"results": results, "meta": {"total_count": len(results)}}


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
