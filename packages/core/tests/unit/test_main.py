"""
Unit tests for main FastAPI application.

Tests for Story 1: API Gateway Foundation
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint returns API information."""
    response = await client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["name"] == "RunLayer Core API"
    assert data["version"] == "0.1.0"
    assert data["description"] == "The trust layer for AI"
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test health check endpoint."""
    response = await client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["version"] == "0.1.0"
    assert data["environment"] == "testing"


@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient):
    """Test metrics endpoint."""
    response = await client.get("/metrics")
    
    assert response.status_code == 200
    data = response.json()
    
    # Basic metrics structure
    assert "http_requests_total" in data
    assert "http_request_duration_seconds" in data
    assert "active_connections" in data
    assert "database_connections" in data


@pytest.mark.asyncio
async def test_cors_headers(client: AsyncClient):
    """Test CORS headers are present."""
    response = await client.options("/", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET"
    })
    
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


@pytest.mark.asyncio
async def test_correlation_id_header(client: AsyncClient):
    """Test correlation ID is added to responses."""
    response = await client.get("/health")
    
    assert response.status_code == 200
    assert "X-Correlation-ID" in response.headers
    
    # Should be a valid UUID format
    correlation_id = response.headers["X-Correlation-ID"]
    assert len(correlation_id) == 36  # UUID length
    assert correlation_id.count("-") == 4  # UUID format


@pytest.mark.asyncio
async def test_response_time_header(client: AsyncClient):
    """Test response time header is added."""
    response = await client.get("/health")
    
    assert response.status_code == 200
    assert "X-Response-Time" in response.headers
    
    # Should be a valid time format
    response_time = response.headers["X-Response-Time"]
    assert response_time.endswith("s")
    assert float(response_time[:-1]) >= 0


@pytest.mark.asyncio
async def test_openapi_docs_available_in_development():
    """Test OpenAPI docs are available in development/testing."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/docs")
        # Should not return 404 in testing environment
        assert response.status_code != 404


@pytest.mark.asyncio
async def test_404_error_handling(client: AsyncClient):
    """Test 404 error handling."""
    response = await client.get("/nonexistent-endpoint")
    
    assert response.status_code == 404
    assert "X-Correlation-ID" in response.headers


@pytest.mark.asyncio
async def test_request_logging_middleware(client: AsyncClient, caplog):
    """Test request logging middleware logs requests."""
    with caplog.at_level("INFO"):
        response = await client.get("/health")
        
    assert response.status_code == 200
    
    # Check that request was logged
    log_messages = [record.message for record in caplog.records]
    assert any("Request started" in msg for msg in log_messages)
    assert any("Request completed" in msg for msg in log_messages)
