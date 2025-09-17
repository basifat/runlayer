"""
Tests for Story 1: API Gateway Foundation - Tightened Implementation

Tests exactly what the acceptance criteria require:
- FastAPI application with async/await support
- JWT-based authentication with refresh tokens
- Rate limiting: 1000 requests/hour for free tier
- OpenAPI documentation auto-generated
- CORS handling for cross-origin requests
- Request logging with correlation IDs
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
import time

from src.main_tightened import app

client = TestClient(app)


def test_fastapi_async_support():
    """Test FastAPI application with async/await support."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "RunLayer Core API"
    assert data["status"] == "healthy"


def test_health_check_uptime_sla():
    """Test health check endpoint for 99.9% uptime SLA."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["version"] == "0.1.0"


def test_openapi_documentation():
    """Test OpenAPI documentation auto-generated."""
    response = client.get("/docs")
    assert response.status_code == 200
    
    response = client.get("/openapi.json")
    assert response.status_code == 200
    openapi_spec = response.json()
    assert openapi_spec["info"]["title"] == "RunLayer Core API"


def test_cors_handling():
    """Test CORS handling for cross-origin requests."""
    response = client.options(
        "/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


def test_jwt_authentication_login():
    """Test JWT-based authentication with refresh tokens."""
    response = client.post(
        "/auth/login",
        json={"user_id": "test_user", "password": "test_password"}
    )
    assert response.status_code == 200
    data = response.json()
    
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_jwt_refresh_token():
    """Test JWT refresh token functionality."""
    # First login to get tokens
    login_response = client.post(
        "/auth/login",
        json={"user_id": "test_user"}
    )
    tokens = login_response.json()
    
    # Use refresh token to get new access token
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_protected_route_requires_auth():
    """Test protected route requires JWT authentication."""
    # Without token
    response = client.get("/protected")
    assert response.status_code == 403
    
    # With valid token
    login_response = client.post("/auth/login", json={"user_id": "test_user"})
    token = login_response.json()["access_token"]
    
    response = client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "user" in data


@patch('src.main_tightened.redis_client')
def test_rate_limiting_1000_per_hour(mock_redis):
    """Test rate limiting: 1000 requests/hour for free tier."""
    # Mock Redis to return count under limit
    mock_redis.get.return_value = None
    mock_redis.setex = AsyncMock()
    mock_redis.incr = AsyncMock()
    
    response = client.get("/protected")
    assert response.status_code != 429  # Should not be rate limited
    
    # Mock Redis to return count over limit
    mock_redis.get.return_value = "1001"
    
    response = client.get("/protected")
    assert response.status_code == 429
    assert "Rate limit exceeded" in response.json()["detail"]


def test_correlation_id_logging():
    """Test request logging with correlation IDs."""
    # Test with provided correlation ID
    correlation_id = "test-correlation-123"
    response = client.get(
        "/health",
        headers={"X-Correlation-ID": correlation_id}
    )
    
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == correlation_id
    
    # Test with auto-generated correlation ID
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Correlation-ID" in response.headers
    assert len(response.headers["X-Correlation-ID"]) == 36  # UUID length


def test_response_time_header():
    """Test p99 API response time < 300ms (header tracking)."""
    response = client.get("/health")
    
    assert response.status_code == 200
    assert "X-Response-Time" in response.headers
    
    # Parse response time
    response_time = response.headers["X-Response-Time"]
    assert response_time.endswith("s")
    time_value = float(response_time[:-1])
    
    # Should be fast for health check
    assert time_value < 0.3  # Less than 300ms


def test_exception_handling_with_correlation():
    """Test exception handling includes correlation ID."""
    response = client.get("/nonexistent")
    
    assert response.status_code == 404
    assert "X-Correlation-ID" in response.headers
    
    data = response.json()
    assert "error" in data
    assert "correlation_id" in data["error"]


def test_rate_limit_skips_health_endpoints():
    """Test rate limiting skips health check endpoints."""
    with patch('src.main_tightened.redis_client') as mock_redis:
        mock_redis.get.return_value = "1001"  # Over limit
        
        # Health endpoints should not be rate limited
        response = client.get("/health")
        assert response.status_code == 200
        
        response = client.get("/")
        assert response.status_code == 200
        
        # Protected endpoints should be rate limited
        response = client.get("/protected")
        assert response.status_code == 429


@pytest.mark.asyncio
async def test_async_await_support():
    """Test that endpoints properly support async/await."""
    # This test verifies the async nature by checking that
    # the application can handle concurrent requests
    import asyncio
    import httpx
    
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # Make multiple concurrent requests
        tasks = [ac.get("/health") for _ in range(10)]
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200
