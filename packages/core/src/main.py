"""
RunLayer Core API - FastAPI Application

Story 1: API Gateway Foundation
- FastAPI application with async/await support
- JWT-based authentication with refresh tokens
- Rate limiting: 1000 requests/hour for free tier
- OpenAPI documentation auto-generated
- CORS handling for cross-origin requests
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

import structlog
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .middleware.auth import AuthMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .middleware.correlation import CorrelationMiddleware
from .routers import auth, users, validators, proofs
from .database import init_db, close_db


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests with correlation IDs and performance metrics."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Get correlation ID from middleware
        correlation_id = getattr(request.state, 'correlation_id', 'unknown')
        
        # Log request start
        logger.info(
            "Request started",
            method=request.method,
            url=str(request.url),
            correlation_id=correlation_id,
            user_agent=request.headers.get("user-agent"),
            client_ip=request.client.host if request.client else None
        )
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log request completion
            logger.info(
                "Request completed",
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
                correlation_id=correlation_id
            )
            
            # Add performance headers
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            response.headers["X-Correlation-ID"] = correlation_id
            
            return response
            
        except Exception as exc:
            duration = time.time() - start_time
            
            logger.error(
                "Request failed",
                method=request.method,
                url=str(request.url),
                duration_ms=round(duration * 1000, 2),
                correlation_id=correlation_id,
                error=str(exc),
                exc_info=True
            )
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting RunLayer Core API", version=settings.VERSION)
    await init_db()
    
    yield
    
    # Shutdown
    logger.info("Shutting down RunLayer Core API")
    await close_db()


# Create FastAPI application
app = FastAPI(
    title="RunLayer Core API",
    description="The trust layer for AI - Validate AI outputs with cryptographic proof",
    version=settings.VERSION,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan
)

# Security middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID", "X-Response-Time"]
)

# Custom middleware (order matters - last added runs first)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(CorrelationMiddleware)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(validators.router, prefix="/api/v1/validators", tags=["Validators"])
app.include_router(proofs.router, prefix="/api/v1/proofs", tags=["Proofs"])


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API information."""
    return {
        "name": "RunLayer Core API",
        "version": settings.VERSION,
        "description": "The trust layer for AI",
        "docs_url": "/docs" if settings.ENVIRONMENT != "production" else None,
        "status": "healthy"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for load balancers."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    """Basic metrics endpoint (Prometheus format in production)."""
    # TODO: Implement proper Prometheus metrics
    return {
        "http_requests_total": 0,
        "http_request_duration_seconds": 0,
        "active_connections": 0,
        "database_connections": 0
    }


# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with structured logging."""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')
    
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        correlation_id=correlation_id,
        method=request.method,
        url=str(request.url)
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "correlation_id": correlation_id
            }
        },
        headers={"X-Correlation-ID": correlation_id}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')
    
    logger.error(
        "Unexpected error",
        error=str(exc),
        correlation_id=correlation_id,
        method=request.method,
        url=str(request.url),
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
                "correlation_id": correlation_id
            }
        },
        headers={"X-Correlation-ID": correlation_id}
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        log_level="info"
    )
