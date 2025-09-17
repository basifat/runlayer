"""
Database configuration and connection management.

Uses SQLAlchemy with async support for PostgreSQL.
"""

import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
import structlog

from .config import get_database_url, settings

logger = structlog.get_logger()

# Database engine
engine = None
SessionLocal = None


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


async def init_db():
    """Initialize database connection."""
    global engine, SessionLocal
    
    database_url = get_database_url()
    logger.info("Initializing database connection", url=database_url.split('@')[0] + '@***')
    
    # Create async engine
    engine = create_async_engine(
        database_url,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=3600,  # Recycle connections every hour
        echo=settings.DEBUG,  # Log SQL queries in debug mode
        # Use NullPool for serverless environments
        poolclass=NullPool if settings.ENVIRONMENT == "production" else None
    )
    
    # Create session factory
    SessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    logger.info("Database connection initialized")


async def close_db():
    """Close database connection."""
    global engine
    
    if engine:
        logger.info("Closing database connection")
        await engine.dispose()
        engine = None
        logger.info("Database connection closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    if not SessionLocal:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def health_check() -> bool:
    """Check database health."""
    try:
        if not engine:
            return False
        
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return False
