"""RunLayer Core API - Story 1: API Gateway Foundation (12-Factor + DRY)

12-Factor App Compliance:
- III. Config: All configuration from environment
- IV. Backing Services: Redis as attached resource
- VI. Processes: Stateless middleware and handlers
- XI. Logs: Treat logs as event streams

DRY Principles Applied:
- Centralized middleware factory
- Reusable authentication patterns
- Single source of truth for configuration
- No code duplication across handlers
"""

import logging
import time
import uuid
from typing import Dict, Any, Optional, Callable
from contextlib import asynccontextmanager
from functools import wraps

from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis
from jose import JWTError, jwt
from datetime import datetime, timedelta

from .config import settings
from .database import init_db, close_db
from .redis import redis_manager, validator_cache, validator_queue
from .validators.api import router as validators_router

# 12-Factor: Logs as event streams
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 12-Factor: Backing services as attached resources
def create_redis_client() -> redis.Redis:
    """Create Redis client with 12-Factor configuration."""
    return redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        retry_on_timeout=True,
        health_check_interval=30
    )

redis_client = create_redis_client()
security = HTTPBearer()

# DRY: Centralized middleware factory
class BaseMiddleware(BaseHTTPMiddleware):
    """DRY: Base middleware with common functionality."""
    
    def __init__(self, app, name: str):
        super().__init__(app)
        self.name = name
        self.logger = logging.getLogger(f"middleware.{name}")
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        correlation_id = getattr(request.state, 'correlation_id', str(uuid.uuid4()))
        
        try:
            response = await self._process_request(request, call_next)
            duration = time.time() - start_time
            self.logger.info(
                f"{self.name} processed request",
                extra={"correlation_id": correlation_id, "duration_ms": duration * 1000}
            )
            return response
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                f"{self.name} failed: {str(e)}",
                extra={"correlation_id": correlation_id, "duration_ms": duration * 1000}
            )
            raise
    
    async def _process_request(self, request: Request, call_next):
        """Override in subclasses."""
        return await call_next(request)


class CorrelationMiddleware(BaseMiddleware):
    """Add correlation ID to all requests (DRY: extends BaseMiddleware)."""
    
    def __init__(self, app):
        super().__init__(app, "correlation")
    
    async def _process_request(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class RateLimitMiddleware(BaseMiddleware):
    """Rate limiting middleware (DRY: extends BaseMiddleware)."""
    
    def __init__(self, app):
        super().__init__(app, "rate_limit")
    
    async def _process_request(self, request: Request, call_next):
        client_ip = request.client.host
        rate_limit_key = f"rate_limit:{client_ip}"
        
        try:
            current_requests = await redis_client.get(rate_limit_key)
            if current_requests is None:
                await redis_client.setex(rate_limit_key, settings.RATE_LIMIT_WINDOW, 1)
            else:
                current_requests = int(current_requests)
                if current_requests >= settings.RATE_LIMIT_REQUESTS:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded. Max {settings.RATE_LIMIT_REQUESTS} requests per {settings.RATE_LIMIT_WINDOW} seconds."
                    )
                await redis_client.incr(rate_limit_key)
        except redis.RedisError as e:
            # 12-Factor: Fail open if backing service unavailable
            self.logger.warning(f"Redis unavailable, skipping rate limiting: {e}")
        
        response = await call_next(request)
        return response


class RequestLoggingMiddleware(BaseMiddleware):
    """Request logging middleware (DRY: extends BaseMiddleware)."""
    
    def __init__(self, app):
        super().__init__(app, "request_logging")
    
    async def _process_request(self, request: Request, call_next):
        start_time = time.time()
        correlation_id = getattr(request.state, 'correlation_id', 'unknown')
        
        self.logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={"correlation_id": correlation_id}
        )
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        self.logger.info(
            f"Request completed: {request.method} {request.url.path} - {response.status_code} - {duration:.3f}s",
            extra={"correlation_id": correlation_id, "duration_ms": duration * 1000}
        )
        
        # Performance monitoring headers
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        response.headers["X-Request-ID"] = correlation_id
        
        return response


# DRY: Centralized JWT service
class JWTService:
    """DRY: Single service for all JWT operations."""
    
    def __init__(self):
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 15
        self.refresh_token_expire_days = 7
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=self.access_token_expire_minutes))
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, data: dict) -> str:
        """Create JWT refresh token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str, token_type: str = "access") -> dict:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != token_type:
                raise JWTError(f"Invalid token type. Expected {token_type}")
            return payload
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Could not validate credentials: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )


# Global JWT service instance
jwt_service = JWTService()


# DRY: Reusable authentication dependency
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get current user from JWT token (DRY: uses centralized service)."""
    payload = jwt_service.verify_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user ID"
        )
    return {"user_id": user_id, "payload": payload}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize and cleanup database and Redis."""
    # Startup
    logger.info("Starting RunLayer Core API")
    await init_db()
    await redis_manager.initialize()
    
    yield
    
    # Shutdown
    logger.info("Shutting down RunLayer Core API")
    await close_db()
    await redis_manager.close()


# Create FastAPI application
app = FastAPI(
    title="RunLayer Core API",
    description="Production-ready API Gateway for RunLayer validator execution platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Include validator API routes
app.include_router(validators_router)

# DRY: Middleware configuration function
def configure_middleware(app: FastAPI) -> None:
    """DRY: Centralized middleware configuration."""
    # Order matters - last added runs first
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(CorrelationMiddleware)
    
    # CORS middleware with 12-Factor config
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "X-Response-Time", "X-Request-ID"]
    )


# Configure middleware
configure_middleware(app)


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API information."""
    return {
        "name": "RunLayer Core API",
        "version": "0.1.0",
        "description": "The trust layer for AI",
        "status": "healthy"
    }


# DRY: Health check with comprehensive status
@app.get("/health")
async def health_check():
    """Health check endpoint for 99.9% uptime SLA (DRY: comprehensive checks)."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
        "services": {}
    }
    
    # Check Redis health
    redis_health = await redis_manager.health_check()
    health_status["services"]["redis"] = redis_health
    if redis_health["status"] != "healthy":
        health_status["status"] = "degraded"
    
    # Check database health (if available)
    try:
        from .database import health_check as db_health_check
        db_healthy = await db_health_check()
        health_status["services"]["database"] = "healthy" if db_healthy else "unhealthy"
        if not db_healthy:
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Return appropriate status code
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)


# DRY: Authentication endpoints using centralized service
@app.post("/auth/login")
async def login(credentials: dict):
    """Login endpoint with JWT token generation (DRY: uses JWTService)."""
    # In a real app, validate credentials against database
    user_id = credentials.get("user_id", "demo_user")
    
    access_token = jwt_service.create_access_token(data={"sub": user_id})
    refresh_token = jwt_service.create_refresh_token(data={"sub": user_id})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": jwt_service.access_token_expire_minutes * 60
    }


@app.post("/auth/refresh")
async def refresh_token(refresh_token: str):
    """Refresh JWT token (DRY: uses JWTService)."""
    payload = jwt_service.verify_token(refresh_token, "refresh")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token - missing user ID"
        )
    
    new_access_token = jwt_service.create_access_token(data={"sub": user_id})
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": jwt_service.access_token_expire_minutes * 60
    }


# DRY: Protected endpoint with enhanced response
@app.get("/protected")
async def protected_endpoint(current_user: dict = Depends(get_current_user)):
    """Example protected endpoint (DRY: uses centralized auth)."""
    return {
        "message": "This is a protected endpoint",
        "user": current_user,
        "server_time": datetime.utcnow().isoformat(),
        "environment": settings.ENVIRONMENT
    }


# DRY: Configuration endpoint for debugging (development only)
@app.get("/config")
async def get_config(current_user: dict = Depends(get_current_user)):
    """Get sanitized configuration (development only)."""
    if settings.ENVIRONMENT != "development":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found"
        )
    
    return {
        "environment": settings.ENVIRONMENT,
        "cors_origins": settings.CORS_ORIGINS,
        "rate_limit_requests": settings.RATE_LIMIT_REQUESTS,
        "rate_limit_window": settings.RATE_LIMIT_WINDOW,
        "log_level": settings.LOG_LEVEL,
        "db_pool_size": settings.DB_POOL_SIZE,
        "db_max_overflow": settings.DB_MAX_OVERFLOW
    }


# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with correlation ID."""
    correlation_id = getattr(request.state, 'correlation_id', str(uuid.uuid4()))
    
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


# 12-Factor: Port binding from environment
if __name__ == "__main__":
    import uvicorn
    import os
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        app, 
        host=host, 
        port=port,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )
