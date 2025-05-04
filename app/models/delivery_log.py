from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from ..database import Base

class DeliveryLog(Base):
    __tablename__ = "delivery_logs"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, index=True)
    webhook_id = Column(String, index=True)
    target_url = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    attempt_number = Column(Integer)
    success = Column(Boolean)
    status_code = Column(Integer, nullable=True)
    error = Column(String, nullable=True)
