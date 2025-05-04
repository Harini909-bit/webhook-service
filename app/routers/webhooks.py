from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime
import requests
import time
from typing import Optional
import logging

# Import your database models and setup
from app.database import get_db
from app.models import Subscription, DeliveryLog

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def deliver_webhook(
    subscription_id: int,
    payload: dict,
    db: Session,
    webhook_id: str,
    attempt: int = 1,
    max_retries: int = 5
):
    """
    Handles webhook delivery with retry mechanism
    """
    try:
        subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not subscription:
            logger.error(f"Subscription {subscription_id} not found")
            return

        # Calculate backoff (10s, 30s, 1m, 5m, 15m)
        backoff = [10, 30, 60, 300, 900][min(attempt-1, 4)]
        
        try:
            # Attempt delivery
            start_time = datetime.utcnow()
            response = requests.post(
                subscription.target_url,
                json=payload,
                timeout=10,
                headers={
                    "User-Agent": "WebhookDeliveryService/1.0",
                    "X-Webhook-Attempt": str(attempt),
                    "X-Webhook-ID": webhook_id
                }
            )
            
            success = response.status_code // 100 == 2
            status_code = response.status_code
            error = None if success else response.text

        except requests.exceptions.RequestException as e:
            success = False
            status_code = None
            error = str(e)

        # Log the attempt
        delivery_log = DeliveryLog(
            subscription_id=subscription_id,
            webhook_id=webhook_id,
            target_url=subscription.target_url,
            attempt_number=attempt,
            success=success,
            status_code=status_code,
            error=error,
            timestamp=datetime.utcnow()
        )
        db.add(delivery_log)
        db.commit()

        # Retry logic
        if not success and attempt < max_retries:
            logger.info(f"Retrying webhook {webhook_id} in {backoff}s (attempt {attempt+1}/{max_retries})")
            time.sleep(backoff)
            await deliver_webhook(
                subscription_id=subscription_id,
                payload=payload,
                db=db,
                webhook_id=webhook_id,
                attempt=attempt+1,
                max_retries=max_retries
            )

    except Exception as e:
        logger.error(f"Error processing webhook {webhook_id}: {str(e)}")
        # Log final failure if we couldn't even record it
        if 'delivery_log' not in locals():
            db.rollback()
            delivery_log = DeliveryLog(
                subscription_id=subscription_id,
                webhook_id=webhook_id,
                target_url="unknown",
                attempt_number=attempt,
                success=False,
                status_code=None,
                error=f"System error: {str(e)}",
                timestamp=datetime.utcnow()
            )
            db.add(delivery_log)
            db.commit()

@router.post("/ingest/{subscription_id}")
async def ingest_webhook(
    subscription_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Endpoint to receive webhooks and initiate delivery
    """
    # Verify subscription exists
    subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Get payload
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Generate unique ID for this webhook
    webhook_id = f"wh_{int(time.time())}_{subscription_id}"

    # Add to background tasks
    background_tasks.add_task(
        deliver_webhook,
        subscription_id=subscription_id,
        payload=payload,
        db=db,
        webhook_id=webhook_id
    )

    logger.info(f"Queued webhook {webhook_id} for delivery to {subscription.target_url}")

    return JSONResponse(
        content={
            "status": "queued",
            "webhook_id": webhook_id,
            "subscription_id": subscription_id
        },
        status_code=202
    )

@router.get("/status/{webhook_id}")
async def get_webhook_status(
    webhook_id: str,
    db: Session = Depends(get_db)
):
    """
    Check delivery status of a webhook
    """
    attempts = db.query(DeliveryLog).filter(
        DeliveryLog.webhook_id == webhook_id
    ).order_by(DeliveryLog.attempt_number).all()

    if not attempts:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return {
        "webhook_id": webhook_id,
        "subscription_id": attempts[0].subscription_id,
        "target_url": attempts[0].target_url,
        "attempts": [
            {
                "attempt_number": a.attempt_number,
                "timestamp": a.timestamp.isoformat(),
                "success": a.success,
                "status_code": a.status_code,
                "error": a.error
            }
            for a in attempts
        ],
        "delivered": any(a.success for a in attempts),
        "final_status": "delivered" if attempts[-1].success else "failed"
    }
