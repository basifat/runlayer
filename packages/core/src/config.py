"""
Configuration for RunLayer Core API - Story 1 Requirements Only

Minimal configuration for exactly what Story 1 needs:
- JWT secret key
- CORS origins
- Redis URL for rate limiting
- Basic environment settings
"""

import os
from typing import List

class Settings:
    """Application settings for Story 1 requirements."""
    
    # JWT Configuration
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY", 
        "your-secret-key-change-in-production-at-least-32-characters"
    )
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",  # Next.js dev server
        "http://localhost:8080",  # Alternative dev port
        "https://runlayer.com",   # Production domain
    ]
    
    # Redis Configuration (for rate limiting)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

settings = Settings()
