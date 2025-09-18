"""
Configuration for RunLayer Core API - Stories 1 & 2

Story 1: JWT, CORS, Redis for rate limiting
Story 2: Database URL for multi-tenant PostgreSQL
"""

import os
from typing import List, Optional

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
    
    # Database Configuration (Story 2)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://localhost/runlayer"
    )
    
    # Redis Configuration (Stories 1 & 3)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_SENTINEL_HOSTS: Optional[str] = os.getenv("REDIS_SENTINEL_HOSTS")  # comma-separated
    REDIS_MASTER_NAME: str = os.getenv("REDIS_MASTER_NAME", "mymaster")
    REDIS_SOCKET_TIMEOUT: int = int(os.getenv("REDIS_SOCKET_TIMEOUT", "5"))
    REDIS_CONNECT_TIMEOUT: int = int(os.getenv("REDIS_CONNECT_TIMEOUT", "5"))
    REDIS_MAX_CONNECTIONS: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "100"))
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()
