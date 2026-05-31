from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost/food_finder"
    google_maps_api_key: str = ""
    yelp_api_key: str = ""
    frontend_url: str = "http://localhost:5173"
    port: int = 8000
    cache_ttl_search: int = 3600
    cache_ttl_reviews: int = 86400

    class Config:
        env_file = ".env"


settings = Settings()
