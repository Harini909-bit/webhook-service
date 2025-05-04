from sqlalchemy import Column, String, Integer
from ..database import Base

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    target_url = Column(String, nullable=False)
    secret = Column(String, nullable=True)
    event_type = Column(String, nullable=True)  # For bonus points
