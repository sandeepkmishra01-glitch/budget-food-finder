from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), index=True)
    item_name = Column(String, nullable=False)
    price = Column(Numeric(5, 2))
    photo_url = Column(String)
    source = Column(String)

    restaurant = relationship("Restaurant", back_populates="menu_items")
