from .database import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    target_url = Column(String)
    secret = Column(String, nullable=True)

class DeliveryLog(Base):
    __tablename__ = "delivery_logs"
    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer)
    webhook_id = Column(String)
    target_url = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    success = Column(Boolean)
    status_code = Column(Integer, nullable=True)
    error = Column(String, nullable=True)
