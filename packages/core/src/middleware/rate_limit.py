"""
Rate limiting middleware using Redis for distributed rate limiting.

Implements sliding window rate limiting with different tiers:
- Free tier: 1000 requests/hour
- Pro tier: 10000 requests/hour
- Enterprise: Custom limits
"""

import time
import json
from typing import Optional
import redis.asyncio as redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from ..config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-based distributed rate limiting middleware."""
    
    def __init__(self, app, redis_url: str = None):
        super().__init__(app)
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_client = None
    
    async def get_redis_client(self):
        """Get or create Redis client."""
        if not self.redis_client:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
        return self.redis_client
    
    async def get_user_tier(self, user_id: Optional[str]) -> str:
        """Get user's subscription tier for rate limiting."""
        if not user_id:
            return "anonymous"
        
        # TODO: Query database for user's subscription tier
        # For now, return free tier for all authenticated users
        return "free"
    
    def get_rate_limits(self, tier: str) -> dict:
        """Get rate limits based on user tier."""
        limits = {
            "anonymous": {
                "requests_per_minute": 10,
                "requests_per_hour": 100,
                "requests_per_day": 1000
            },
            "free": {
                "requests_per_minute": settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
                "requests_per_hour": settings.RATE_LIMIT_REQUESTS_PER_HOUR,
                "requests_per_day": settings.RATE_LIMIT_REQUESTS_PER_DAY
            },
            "pro": {
                "requests_per_minute": 200,
                "requests_per_hour": 10000,
                "requests_per_day": 100000
            },
            "enterprise": {
                "requests_per_minute": 1000,
                "requests_per_hour": 50000,
                "requests_per_day": 500000
            }
        }
        return limits.get(tier, limits["anonymous"])
    
    def get_client_identifier(self, request: Request) -> str:
        """Get unique identifier for rate limiting."""
        # Try to get user ID from request state (set by auth middleware)
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            return f"user:{user_id}"
        
        # Fall back to IP address for anonymous users
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
    
    async def check_rate_limit(self, identifier: str, limits: dict) -> tuple[bool, dict]:
        """Check if request is within rate limits using sliding window."""
        redis_client = await self.get_redis_client()
        current_time = int(time.time())
        
        # Check each time window
        windows = [
            ("minute", 60, limits["requests_per_minute"]),
            ("hour", 3600, limits["requests_per_hour"]),
            ("day", 86400, limits["requests_per_day"])
        ]
        
        for window_name, window_seconds, limit in windows:
            key = f"rate_limit:{identifier}:{window_name}"
            window_start = current_time - window_seconds
            
            # Use Redis sorted set for sliding window
            pipe = redis_client.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(key, window_seconds)
            
            results = await pipe.execute()
            current_count = results[1]
            
            if current_count >= limit:
                # Rate limit exceeded
                remaining = 0
                reset_time = current_time + window_seconds
                
                return False, {
                    "error": "Rate limit exceeded",
                    "limit": limit,
                    "remaining": remaining,
                    "reset": reset_time,
                    "window": window_name
                }
        
        # All windows passed, calculate remaining requests
        # Use the most restrictive window for remaining count
        minute_key = f"rate_limit:{identifier}:minute"
        minute_count = await redis_client.zcard(minute_key)
        remaining = max(0, limits["requests_per_minute"] - minute_count)
        
        return True, {
            "limit": limits["requests_per_minute"],
            "remaining": remaining,
            "reset": current_time + 60
        }
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and metrics
        if request.url.path in ["/health", "/metrics"]:
            return await call_next(request)
        
        try:
            # Get client identifier and tier
            identifier = self.get_client_identifier(request)
            user_id = getattr(request.state, 'user_id', None)
            tier = await self.get_user_tier(user_id)
            limits = self.get_rate_limits(tier)
            
            # Check rate limit
            allowed, info = await self.check_rate_limit(identifier, limits)
            
            if not allowed:
                # Rate limit exceeded
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": 429,
                            "message": info["error"],
                            "details": {
                                "limit": info["limit"],
                                "remaining": info["remaining"],
                                "reset": info["reset"],
                                "window": info["window"]
                            }
                        }
                    },
                    headers={
                        "X-RateLimit-Limit": str(info["limit"]),
                        "X-RateLimit-Remaining": str(info["remaining"]),
                        "X-RateLimit-Reset": str(info["reset"]),
                        "Retry-After": str(info["reset"] - int(time.time()))
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers to successful responses
            response.headers["X-RateLimit-Limit"] = str(info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
            response.headers["X-RateLimit-Reset"] = str(info["reset"])
            
            return response
            
        except Exception as e:
            # If rate limiting fails, allow the request but log the error
            import structlog
            logger = structlog.get_logger()
            logger.error("Rate limiting error", error=str(e), exc_info=True)
            
            return await call_next(request)
