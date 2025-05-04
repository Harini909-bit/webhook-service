from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..models import Subscription, DeliveryLog
import requests
from datetime import datetime
import time

celery_app = Celery('tasks', broker_url = 'redis://kv-store-url:6379')

# Database setup for workers
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:postgres@db:5432/webhook_db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@celery_app.task(bind=True, max_retries=5)
def deliver_webhook(self, subscription_id, payload):
    db = SessionLocal()
    
    try:
        subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not subscription:
            raise ValueError("Subscription not found")
        
        # Attempt delivery
        attempt_number = self.request.retries + 1
        try:
            response = requests.post(
                subscription.target_url,
                json=payload,
                timeout=10
            )
            success = response.status_code // 100 == 2
            status_code = response.status_code
            error = None if success else response.text
        except Exception as e:
            success = False
            status_code = None
            error = str(e)
        
        # Log attempt
        log = DeliveryLog(
            subscription_id=subscription_id,
            webhook_id=self.request.id,
            target_url=subscription.target_url,
            attempt_number=attempt_number,
            success=success,
            status_code=status_code,
            error=error
        )
        db.add(log)
        db.commit()
        
        # Retry if failed
        if not success:
            raise self.retry(exc=Exception(error), countdown=min(10 * (2 ** attempt_number), 900))
        
        return {"status": "delivered"}
    finally:
        db.close()
