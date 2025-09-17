"""
Unit tests for middleware components.

Tests for Story 1: API Gateway Foundation middleware
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

from src.middleware.correlation import CorrelationMiddleware
from src.middleware.auth import AuthMiddleware
from src.middleware.rate_limit import RateLimitMiddleware


@pytest.mark.asyncio
async def test_correlation_middleware_generates_id(client: AsyncClient):
    """Test correlation middleware generates correlation ID when not provided."""
    response = await client.get("/health")
    
    correlation_id = response.headers.get("X-Correlation-ID")
    assert correlation_id is not None
    
    # Should be valid UUID format
    uuid.UUID(correlation_id)  # Will raise ValueError if invalid


@pytest.mark.asyncio
async def test_correlation_middleware_preserves_existing_id(client: AsyncClient):
    """Test correlation middleware preserves existing correlation ID."""
    test_correlation_id = str(uuid.uuid4())
    
    response = await client.get("/health", headers={
        "X-Correlation-ID": test_correlation_id
    })
    
    assert response.headers["X-Correlation-ID"] == test_correlation_id


@pytest.mark.asyncio
async def test_auth_middleware_allows_public_routes(client: AsyncClient):
    """Test auth middleware allows access to public routes."""
    public_routes = ["/", "/health", "/metrics"]
    
    for route in public_routes:
        response = await client.get(route)
        # Should not return 401 Unauthorized
        assert response.status_code != 401


@pytest.mark.asyncio
async def test_auth_middleware_blocks_protected_routes(client: AsyncClient):
    """Test auth middleware blocks access to protected routes."""
    # Try to access a protected route without token
    response = await client.get("/api/v1/users/profile")
    
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["message"] == "Missing authentication token"


@pytest.mark.asyncio
async def test_auth_middleware_validates_bearer_token(client: AsyncClient):
    """Test auth middleware validates Bearer token format."""
    # Invalid token format
    response = await client.get("/api/v1/users/profile", headers={
        "Authorization": "InvalidFormat token123"
    })
    
    assert response.status_code == 401


@pytest.mark.asyncio
@patch('src.middleware.rate_limit.redis')
async def test_rate_limit_middleware_allows_within_limits(mock_redis, client: AsyncClient):
    """Test rate limit middleware allows requests within limits."""
    # Mock Redis to return low count
    mock_redis_client = AsyncMock()
    mock_redis_client.pipeline.return_value.execute.return_value = [None, 5, None, None]
    mock_redis_client.zcard.return_value = 5
    mock_redis.from_url.return_value = mock_redis_client
    
    response = await client.get("/health")
    
    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers


@pytest.mark.asyncio
@patch('src.middleware.rate_limit.redis')
async def test_rate_limit_middleware_blocks_over_limits(mock_redis, client: AsyncClient):
    """Test rate limit middleware blocks requests over limits."""
    # Mock Redis to return high count (over limit)
    mock_redis_client = AsyncMock()
    mock_redis_client.pipeline.return_value.execute.return_value = [None, 1000, None, None]
    mock_redis.from_url.return_value = mock_redis_client
    
    response = await client.get("/api/v1/users/profile")
    
    assert response.status_code == 429
    data = response.json()
    assert data["error"]["code"] == 429
    assert "Rate limit exceeded" in data["error"]["message"]


@pytest.mark.asyncio
async def test_rate_limit_middleware_skips_health_endpoints(client: AsyncClient):
    """Test rate limit middleware skips health check endpoints."""
    # Health endpoints should never be rate limited
    response = await client.get("/health")
    assert response.status_code == 200
    
    response = await client.get("/metrics")
    assert response.status_code == 200


class TestAuthMiddleware:
    """Test cases for AuthMiddleware class methods."""
    
    def test_is_public_route(self):
        """Test public route detection."""
        middleware = AuthMiddleware(None)
        
        # Exact matches
        assert middleware.is_public_route("/") is True
        assert middleware.is_public_route("/health") is True
        assert middleware.is_public_route("/api/v1/auth/login") is True
        
        # Pattern matches
        assert middleware.is_public_route("/api/v1/proofs/public/123") is True
        assert middleware.is_public_route("/static/css/style.css") is True
        
        # Protected routes
        assert middleware.is_public_route("/api/v1/users/profile") is False
        assert middleware.is_public_route("/api/v1/validators") is False
    
    def test_extract_token(self):
        """Test token extraction from Authorization header."""
        from starlette.requests import Request
        from starlette.datastructures import Headers
        
        middleware = AuthMiddleware(None)
        
        # Valid Bearer token
        headers = Headers({"authorization": "Bearer valid-token-123"})
        request = Request({"type": "http", "headers": headers.raw})
        token = middleware.extract_token(request)
        assert token == "valid-token-123"
        
        # Invalid format
        headers = Headers({"authorization": "InvalidFormat token123"})
        request = Request({"type": "http", "headers": headers.raw})
        token = middleware.extract_token(request)
        assert token is None
        
        # Missing header
        headers = Headers({})
        request = Request({"type": "http", "headers": headers.raw})
        token = middleware.extract_token(request)
        assert token is None


class TestRateLimitMiddleware:
    """Test cases for RateLimitMiddleware class methods."""
    
    def test_get_rate_limits(self):
        """Test rate limit configuration by tier."""
        middleware = RateLimitMiddleware(None)
        
        # Anonymous users
        limits = middleware.get_rate_limits("anonymous")
        assert limits["requests_per_minute"] == 10
        assert limits["requests_per_hour"] == 100
        
        # Free tier
        limits = middleware.get_rate_limits("free")
        assert limits["requests_per_minute"] == 60  # From settings
        assert limits["requests_per_hour"] == 1000
        
        # Pro tier
        limits = middleware.get_rate_limits("pro")
        assert limits["requests_per_minute"] == 200
        assert limits["requests_per_hour"] == 10000
        
        # Enterprise tier
        limits = middleware.get_rate_limits("enterprise")
        assert limits["requests_per_minute"] == 1000
        assert limits["requests_per_hour"] == 50000
    
    def test_get_client_identifier(self):
        """Test client identifier generation."""
        from starlette.requests import Request
        from starlette.datastructures import Address
        
        middleware = RateLimitMiddleware(None)
        
        # With user ID in request state
        request = Request({"type": "http"})
        request.state.user_id = "user123"
        identifier = middleware.get_client_identifier(request)
        assert identifier == "user:user123"
        
        # Without user ID, use IP
        request = Request({
            "type": "http",
            "client": Address("192.168.1.1", 12345)
        })
        identifier = middleware.get_client_identifier(request)
        assert identifier == "ip:192.168.1.1"
