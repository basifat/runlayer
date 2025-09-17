"""12-Factor App Configuration for RunLayer Core API

Follows 12-Factor App principles:
- III. Config: Store config in environment variables
- Explicit dependencies and backing services
- Environment-first configuration (no hardcoded defaults in production)
"""

import os
from typing import List, Optional
from functools import lru_cache
from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """12-Factor App settings - environment-first configuration."""
    
    # III. Config - Store config in environment
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    
    # JWT Configuration (Story 1) - Required in production
    JWT_SECRET_KEY: str = Field(
        default="dev-secret-key-change-in-production",
        env="JWT_SECRET_KEY",
        min_length=32
    )
    
    # CORS Configuration (Story 1) - Environment-specific
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:8080",
        env="CORS_ORIGINS"
    )
    
    # Backing Services - Treat as attached resources
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://localhost/runlayer", 
        env="DATABASE_URL"
    )
    
    # Database Pool Configuration (12-Factor: explicit resource limits)
    DB_POOL_SIZE: int = Field(default=20, env="DB_POOL_SIZE")
    DB_MAX_OVERFLOW: int = Field(default=30, env="DB_MAX_OVERFLOW")
    DB_POOL_TIMEOUT: int = Field(default=30, env="DB_POOL_TIMEOUT")
    DB_POOL_RECYCLE: int = Field(default=3600, env="DB_POOL_RECYCLE")
    
    # Rate Limiting Configuration
    RATE_LIMIT_REQUESTS: int = Field(default=1000, env="RATE_LIMIT_REQUESTS")
    RATE_LIMIT_WINDOW: int = Field(default=3600, env="RATE_LIMIT_WINDOW")
    
    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v: str) -> List[str]:
        """Parse comma-separated CORS origins."""
        return [origin.strip() for origin in v.split(",")]
    
    @validator("JWT_SECRET_KEY")
    def validate_jwt_secret_production(cls, v: str, values: dict) -> str:
        """Ensure JWT secret is secure in production."""
        env = values.get("ENVIRONMENT", "development")
        if env == "production" and v == "dev-secret-key-change-in-production":
            raise ValueError("JWT_SECRET_KEY must be set in production")
        return v
    
    @validator("DATABASE_URL")
    def validate_database_url_production(cls, v: str, values: dict) -> str:
        """Ensure database URL is configured in production."""
        env = values.get("ENVIRONMENT", "development")
        if env == "production" and "localhost" in v:
            raise ValueError("DATABASE_URL must not use localhost in production")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance (DRY - single source of truth)."""
    return Settings()


# Global settings instance
settings = get_settings()
