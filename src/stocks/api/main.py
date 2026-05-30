from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from loguru import logger
from stocks.config import Config

# Load config statically
config = Config.load()

# Initialize FastAPI with metadata
app = FastAPI(
    title="NSE Stock Analysis Platform API",
    description="Production-grade FastAPI back-end providing stock explorer, multi-pane financial charts, technical indicators, screening snapshot sweeps, and dynamic data synchronizations.",
    version="1.0.0"
)

# 1. CORS Middleware Configuration
# Allows React 19 front-end (typically running on localhost) to connect cleanly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Parameterized as '*' for local terminal ease, can restrict to front-end port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Gzip Compression Middleware
# Mandatory to speed up large historical EOD pricing JSON arrays (740+ candles) over the wire
app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.get("/health")
def health_check():
    """Simple check to verify the API service status and configuration loading."""
    return {
        "status": "HEALTHY",
        "app_name": config.app.name,
        "environment": config.app.env
    }

# 3. Dynamic route registration
from stocks.api.v1.router import api_router
app.include_router(api_router)
