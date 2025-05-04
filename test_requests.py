import requests

BASE_URL = "http://localhost:8000"

# Create subscription
print("Creating subscription:")
print(requests.post(
    f"{BASE_URL}/subscriptions/",
    json={"target_url": "http://localhost:9000/webhook", "secret": "test123"}
).json())

# Send webhook
print("\nSending webhook:")
print(requests.post(
    f"{BASE_URL}/webhooks/1",
    json={"event": "test", "data": "value"}
).json())

# Check logs
print("\nChecking logs:")
print(requests.get(f"{BASE_URL}/logs/1").json())
