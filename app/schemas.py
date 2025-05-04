from pydantic import BaseModel

class SubscriptionCreate(BaseModel):
    target_url: str
    secret: str = None

class WebhookCreate(BaseModel):
    payload: dict
