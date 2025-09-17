"""
Configuration for RunLayer Core API - Stories 1 & 2

Story 1: JWT, CORS, Redis for rate limiting
Story 2: Database URL for multi-tenant PostgreSQL
"""

import os
from typing import List

class Settings:
    """Application settings for Stories 1 & 2."""
    
    # JWT Configuration (Story 1)
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY", 
        "your-secret-key-change-in-production-at-least-32-characters"
    )
    
    # CORS Configuration (Story 1)
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",  # Next.js dev server
        "http://localhost:8080",  # Alternative dev port
        "https://runlayer.com",   # Production domain
    ]
    
    # Redis Configuration (Story 1)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Database Configuration (Story 2)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://localhost/runlayer"
    )
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

settings = Settings()
