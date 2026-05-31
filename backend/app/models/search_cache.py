from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base


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
