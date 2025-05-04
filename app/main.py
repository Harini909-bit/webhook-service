from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Security, Request
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import requests
import uuid
import time
import hmac
import hashlib
from typing import Optional

from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env file

# Safe environment variable handling
API_KEYS = os.getenv("API_KEYS", "").split(",") if os.getenv("API_KEYS") else []
VALID_API_KEYS = {key.strip(): f"user-{i}" for i, key in enumerate(API_KEYS, 1)} if API_KEYS else {"test-key": "test-user"}

# Import database and models
from .database import SessionLocal, engine
from .models import Base, Subscription, DeliveryLog
from .schemas import SubscriptionCreate, WebhookCreate

# Initialize FastAPI
app = FastAPI(title="Webhook Delivery Service")

# Create tables
Base.metadata.create_all(bind=engine)

# API Key Authentication Setup
API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# This would ideally come from environment variables
VALID_API_KEYS = {
    "your-secret-key-here": "admin",
    "another-valid-key": "client"
}

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key"
        )
    return api_key

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Webhook Delivery with Retry Mechanism
async def deliver_webhook(
    subscription_id: int,
    payload: dict,
    db: Session,
    webhook_id: str,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0
):
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not subscription:
        raise ValueError(f"Subscription {subscription_id} not found")

    current_delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            # Create HMAC signature if secret exists
            headers = {"Content-Type": "application/json"}
            if subscription.secret:
                signature = hmac.new(
                    subscription.secret.encode(),
                    str(payload).encode(),
                    hashlib.sha256
                ).hexdigest()
                headers["X-Webhook-Signature"] = f"sha256={signature}"

            # Attempt delivery
            response = requests.post(
                subscription.target_url,
                json=payload,
                headers=headers,
                timeout=10
            )
            success = response.status_code // 100 == 2

            # Log attempt
            log = DeliveryLog(
                subscription_id=subscription_id,
                webhook_id=webhook_id,
                target_url=subscription.target_url,
                attempt_number=attempt + 1,
                success=success,
                status_code=response.status_code,
                error=None if success else response.text,
                timestamp=datetime.utcnow()
            )
            db.add(log)
            db.commit()

            if success:
                return True

        except Exception as e:
            # Log failure
            log = DeliveryLog(
                subscription_id=subscription_id,
                webhook_id=webhook_id,
                target_url=subscription.target_url,
                attempt_number=attempt + 1,
                success=False,
                status_code=None,
                error=str(e),
                timestamp=datetime.utcnow()
            )
            db.add(log)
            db.commit()

        # Exponential backoff before next retry
        if attempt < max_retries - 1:
            time.sleep(current_delay)
            current_delay *= backoff_factor

    return False

# API Endpoints
@app.post("/subscriptions/", status_code=201)
async def create_subscription(
    subscription: SubscriptionCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """Create a new webhook subscription"""
    db_subscription = Subscription(
        target_url=subscription.target_url,
        secret=subscription.secret
    )
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription

@app.post("/webhooks/{subscription_id}")
async def ingest_webhook(
    subscription_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """Ingest a webhook and queue for delivery"""
    # Verify subscription exists
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Get payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Generate unique ID for this webhook
    webhook_id = str(uuid.uuid4())

    # Queue background delivery task
    background_tasks.add_task(
        deliver_webhook,
        subscription_id=subscription_id,
        payload=payload,
        db=db,
        webhook_id=webhook_id
    )

    return JSONResponse(
        content={
            "status": "queued",
            "webhook_id": webhook_id,
            "subscription_id": subscription_id
        },
        status_code=202
    )

@app.get("/deliveries/{webhook_id}")
async def get_delivery_status(
    webhook_id: str,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """Check delivery status of a webhook"""
    attempts = db.query(DeliveryLog).filter(
        DeliveryLog.webhook_id == webhook_id
    ).order_by(DeliveryLog.attempt_number).all()

    if not attempts:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return {
        "webhook_id": webhook_id,
        "subscription_id": attempts[0].subscription_id,
        "status": "delivered" if any(a.success for a in attempts) else "failed",
        "attempts": [
            {
                "attempt": a.attempt_number,
                "timestamp": a.timestamp.isoformat(),
                "success": a.success,
                "status_code": a.status_code,
                "error": a.error
            }
            for a in attempts
        ]
    }

# Health check endpoint (unauthenticated)
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/debug/keys")
async def debug_keys():
    return {"valid_keys": list(VALID_API_KEYS.keys())}
