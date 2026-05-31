from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime, ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


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

    restaurant = relationship("Restaurant", back_populates="review_caches")
