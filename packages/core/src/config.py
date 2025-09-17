"""
Configuration management for RunLayer Core API.

Uses Pydantic Settings for type-safe configuration with environment variable support.
"""

import os
from typing import List, Optional
from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=False, env="DEBUG")
    
    # Server
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    ALLOWED_HOSTS: List[str] = Field(default=["*"], env="ALLOWED_HOSTS")
    
    # CORS
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"],
        env="CORS_ORIGINS"
    )
    
    # Database
    DATABASE_URL: str = Field(env="DATABASE_URL")
    DATABASE_POOL_SIZE: int = Field(default=20, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(default=30, env="DATABASE_MAX_OVERFLOW")
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    REDIS_POOL_SIZE: int = Field(default=20, env="REDIS_POOL_SIZE")
    
    # JWT Authentication
    JWT_SECRET_KEY: str = Field(env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, env="JWT_REFRESH_TOKEN_EXPIRE_DAYS")
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=60, env="RATE_LIMIT_REQUESTS_PER_MINUTE")
    RATE_LIMIT_REQUESTS_PER_HOUR: int = Field(default=1000, env="RATE_LIMIT_REQUESTS_PER_HOUR")
    RATE_LIMIT_REQUESTS_PER_DAY: int = Field(default=10000, env="RATE_LIMIT_REQUESTS_PER_DAY")
    
    # AWS
    AWS_REGION: str = Field(default="us-east-1", env="AWS_REGION")
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    
    # S3 Storage
    S3_BUCKET_NAME: str = Field(env="S3_BUCKET_NAME")
    S3_REGION: str = Field(default="us-east-1", env="S3_REGION")
    
    # Temporal (for validator execution)
    TEMPORAL_HOST: str = Field(default="localhost:7233", env="TEMPORAL_HOST")
    TEMPORAL_NAMESPACE: str = Field(default="default", env="TEMPORAL_NAMESPACE")
    
    # Monitoring
    SENTRY_DSN: Optional[str] = Field(default=None, env="SENTRY_DSN")
    DATADOG_API_KEY: Optional[str] = Field(default=None, env="DATADOG_API_KEY")
    
    # Feature Flags
    ENABLE_REGISTRATION: bool = Field(default=True, env="ENABLE_REGISTRATION")
    ENABLE_VALIDATOR_EXECUTION: bool = Field(default=True, env="ENABLE_VALIDATOR_EXECUTION")
    ENABLE_PUBLIC_PROOFS: bool = Field(default=True, env="ENABLE_PUBLIC_PROOFS")
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("ALLOWED_HOSTS", pre=True)
    def parse_allowed_hosts(cls, v):
        """Parse allowed hosts from string or list."""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        """Validate database URL format."""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        return v
    
    @validator("JWT_SECRET_KEY")
    def validate_jwt_secret(cls, v):
        """Validate JWT secret key strength."""
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long")
        return v
    
    class Config:
        """Pydantic config."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


def get_database_url() -> str:
    """Get database URL for SQLAlchemy."""
    url = settings.DATABASE_URL
    if url.startswith("postgresql://"):
        # Convert to asyncpg format
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def get_redis_url() -> str:
    """Get Redis URL."""
    return settings.REDIS_URL


def is_development() -> bool:
    """Check if running in development mode."""
    return settings.ENVIRONMENT == "development"


def is_production() -> bool:
    """Check if running in production mode."""
    return settings.ENVIRONMENT == "production"


def is_testing() -> bool:
    """Check if running in test mode."""
    return settings.ENVIRONMENT == "testing"
