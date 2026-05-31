WEIGHT_RATING = 0.40
WEIGHT_REVIEWS = 0.30
WEIGHT_PRICE = 0.20
WEIGHT_TRAVEL = 0.10

MAX_RATING = 5.0
MAX_REVIEW_COUNT = 1000
MAX_TRAVEL_MINUTES = 45


def rank_results(restaurants: list[dict]) -> list[dict]:
    for r in restaurants:
        r["score"] = _compute_score(r)

    restaurants.sort(key=lambda r: r["score"], reverse=True)
    return restaurants


def _compute_score(restaurant: dict) -> float:
    rating_score = (restaurant.get("rating", 0) / MAX_RATING) * WEIGHT_RATING

    review_count = min(restaurant.get("review_count", 0), MAX_REVIEW_COUNT)
    review_score = (review_count / MAX_REVIEW_COUNT) * WEIGHT_REVIEWS

    price_level = restaurant.get("price_level", "$$")
    price_score = _price_value_score(price_level) * WEIGHT_PRICE

    travel_min = restaurant.get("travel_time_minutes", MAX_TRAVEL_MINUTES)
    travel_score = (
        (MAX_TRAVEL_MINUTES - travel_min) / MAX_TRAVEL_MINUTES
    ) * WEIGHT_TRAVEL

    return rating_score + review_score + price_score + travel_score


def _price_value_score(price_level: str | None) -> float:
    mapping = {"$": 1.0, "$$": 0.6, "$$$": 0.3, "$$$$": 0.1}
    return mapping.get(price_level or "$$", 0.5)
