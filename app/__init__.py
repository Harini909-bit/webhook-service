# app/__init__.py
from .main import app  # Import the FastAPI app instance

__all__ = ["app"]  # Explicit exports

# Optional: Package version
__version__ = "1.0.0"
