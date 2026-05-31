from typing import Literal

from pydantic import BaseModel


class SearchRequest(BaseModel):
    address: str
    travel_mode: Literal["walking", "transit", "driving"] = "driving"


class DishResult(BaseModel):
    name: str
    price: float | None = None
    photo_url: str | None = None


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
    dishes: list[DishResult] = []
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
