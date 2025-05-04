from fastapi import FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# API Key Configuration
API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Key setup - with test keys as fallback
API_KEYS = os.getenv("API_KEYS", "test-key,another-key").split(",")
VALID_API_KEYS = {key.strip(): f"user-{i}" for i, key in enumerate(API_KEYS, 1)}

# Debug endpoint (must come AFTER app creation)
@app.get("/debug/keys", include_in_schema=False)
async def debug_keys():
    return {
        "valid_keys": list(VALID_API_KEYS.keys()),
        "note": "For development only - remove in production"
    }

# Authentication dependency
async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key"
        )
    return api_key

# Test protected endpoint
@app.get("/protected-test")
async def protected_test(api_key: str = Depends(get_api_key)):
    return {
        "status": "access_granted",
        "user": VALID_API_KEYS.get(api_key),
        "note": "This is just a test endpoint"
    }
