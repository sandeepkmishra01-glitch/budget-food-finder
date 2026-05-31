from fastapi import APIRouter

router = APIRouter()

CUISINES = [
    {"key": "all", "label": "All", "emoji": "🍱"},
    {"key": "mexican", "label": "Mexican", "emoji": "🌮"},
    {"key": "pizza", "label": "Pizza", "emoji": "🍕"},
    {"key": "burgers", "label": "Burgers", "emoji": "🍔"},
    {"key": "asian", "label": "Asian", "emoji": "🍜"},
    {"key": "healthy", "label": "Healthy", "emoji": "🥗"},
    {"key": "chicken", "label": "Chicken", "emoji": "🍗"},
    {"key": "wraps", "label": "Wraps", "emoji": "🌯"},
    {"key": "sandwiches", "label": "Sandwiches", "emoji": "🥪"},
    {"key": "sushi", "label": "Sushi", "emoji": "🍣"},
    {"key": "indian", "label": "Indian", "emoji": "🍛"},
    {"key": "mediterranean", "label": "Mediterranean", "emoji": "🥙"},
    {"key": "italian", "label": "Italian", "emoji": "🍝"},
    {"key": "cafe", "label": "Café/Bakery", "emoji": "☕"},
    {"key": "bbq", "label": "BBQ", "emoji": "🌶️"},
]


@router.get("/cuisines")
async def get_cuisines():
    return CUISINES
