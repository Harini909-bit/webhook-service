from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from ..models.subscription import Subscription
from ..database import get_db
from ..schemas import SubscriptionCreate, SubscriptionResponse

router = APIRouter()

@router.post("/", response_model=SubscriptionResponse)
def create_subscription(subscription: SubscriptionCreate, db: Session = Depends(get_db)):
    db_subscription = Subscription(**subscription.dict())
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription

# Add GET, PUT, DELETE endpoints similarly
