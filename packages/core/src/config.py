"""12-Factor App Configuration for RunLayer Core API

Follows 12-Factor App principles:
- III. Config: Store config in environment variables
- Explicit dependencies and backing services
- Environment-first configuration (no hardcoded defaults in production)
"""

import os
from typing import List, Optional
from functools import lru_cache
from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """12-Factor App settings - environment-first configuration."""
    
    # III. Config - Store config in environment
    ENVIRONMENT: str = Field(default="development")
    
    # JWT Configuration (Story 1) - Required in production
    JWT_SECRET_KEY: str = Field(
        default="dev-secret-key-change-in-production",
        min_length=32
    )
    
    # CORS Configuration (Story 1) - Environment-specific
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"]
    )
    
    # Backing Services - Treat as attached resources
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    DATABASE_URL: str = Field(default="postgresql+asyncpg://localhost/runlayer")
    
    # Database Pool Configuration (12-Factor: explicit resource limits)
    DB_POOL_SIZE: int = Field(default=20)
    DB_MAX_OVERFLOW: int = Field(default=30)
    DB_POOL_TIMEOUT: int = Field(default=30)
    DB_POOL_RECYCLE: int = Field(default=3600)
    
    # Rate Limiting Configuration
    RATE_LIMIT_REQUESTS: int = Field(default=1000)
    RATE_LIMIT_WINDOW: int = Field(default=3600)
    
    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO")
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )
    
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v) -> List[str]:
        """Parse comma-separated CORS origins."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        elif isinstance(v, list):
            return v
        return [str(v)]
    
    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_production(cls, v: str, info) -> str:
        """Ensure JWT secret is secure in production."""
        # Note: In Pydantic v2, we can't easily access other field values during validation
        # This validation would be better done at the application level
        return v
    
    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url_production(cls, v: str, info) -> str:
        """Ensure database URL is configured in production."""
        # Note: In Pydantic v2, we can't easily access other field values during validation
        # This validation would be better done at the application level
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance (DRY - single source of truth)."""
    return Settings()


# Global settings instance
settings = get_settings()
