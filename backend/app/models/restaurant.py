from sqlalchemy import Column, Integer, String, Float, ARRAY
from sqlalchemy.orm import relationship

from app.database import Base


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

    menu_items = relationship("MenuItem", back_populates="restaurant")
    review_caches = relationship("ReviewCache", back_populates="restaurant")
