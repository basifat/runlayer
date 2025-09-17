"""
Tests for Story 1: API Gateway Foundation - Main User Flow Coverage

Tests the complete user journey and acceptance criteria:
1. User accesses API documentation
2. User authenticates with JWT tokens
3. User makes authenticated requests
4. Rate limiting protects the API
5. CORS enables cross-origin access
6. Health checks ensure 99.9% uptime
7. Request correlation tracking works
"""

import pytest
import asyncio
import time
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
import redis.asyncio as redis

from src.main import app, jwt_service, redis_client
from src.config import settings


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock = AsyncMock()
    mock.get.return_value = None
    mock.setex.return_value = True
    mock.incr.return_value = 1
    mock.ping.return_value = True
    return mock


class TestMainUserFlows:
    """Test main user flows for API Gateway."""
    
    def test_user_flow_1_api_discovery(self, client):
        """User Flow 1: Developer discovers API through documentation."""
        # Step 1: Access root endpoint
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "RunLayer Core API"
        assert data["status"] == "healthy"
        
        # Step 2: Access OpenAPI documentation
        response = client.get("/docs")
        assert response.status_code == 200
        
        # Step 3: Get OpenAPI spec
        response = client.get("/openapi.json")
        assert response.status_code == 200
        spec = response.json()
        assert spec["info"]["title"] == "RunLayer Core API"
        assert "paths" in spec
        assert "/auth/login" in spec["paths"]
        assert "/protected" in spec["paths"]
    
    def test_user_flow_2_authentication_journey(self, client):
        """User Flow 2: Complete authentication journey."""
        # Step 1: Login with credentials
        login_data = {"user_id": "test_user"}
        response = client.post("/auth/login", json=login_data)
        assert response.status_code == 200
        
        auth_data = response.json()
        assert "access_token" in auth_data
        assert "refresh_token" in auth_data
        assert auth_data["token_type"] == "bearer"
        assert "expires_in" in auth_data
        
        access_token = auth_data["access_token"]
        refresh_token = auth_data["refresh_token"]
        
        # Step 2: Use access token for protected endpoint
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/protected", headers=headers)
        assert response.status_code == 200
        
        protected_data = response.json()
        assert protected_data["message"] == "This is a protected endpoint"
        assert protected_data["user"]["user_id"] == "test_user"
        assert "server_time" in protected_data
        
        # Step 3: Refresh token when needed
        response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 200
        
        refresh_data = response.json()
        assert "access_token" in refresh_data
        assert refresh_data["token_type"] == "bearer"
    
    @patch('src.main.redis_client')
    def test_user_flow_3_rate_limiting_protection(self, mock_redis_client, client):
        """User Flow 3: Rate limiting protects API from abuse."""
        # Mock Redis responses for rate limiting
        mock_redis_client.get = AsyncMock(return_value=None)
        mock_redis_client.setex = AsyncMock(return_value=True)
        mock_redis_client.incr = AsyncMock(return_value=1)
        
        # Step 1: Normal requests work fine
        for i in range(5):
            response = client.get("/")
            assert response.status_code == 200
        
        # Step 2: Simulate rate limit exceeded
        mock_redis_client.get = AsyncMock(return_value=str(settings.RATE_LIMIT_REQUESTS + 1))
        
        response = client.get("/")
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["detail"]
    
    def test_user_flow_4_cors_cross_origin_access(self, client):
        """User Flow 4: CORS enables cross-origin requests."""
        # Step 1: Preflight OPTIONS request
        headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,Authorization"
        }
        response = client.options("/auth/login", headers=headers)
        assert response.status_code == 200
        
        # Step 2: Actual cross-origin request
        headers = {"Origin": "http://localhost:3000"}
        response = client.get("/", headers=headers)
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
    
    @patch('src.main.redis_client')
    def test_user_flow_5_health_monitoring_uptime(self, mock_redis_client, client):
        """User Flow 5: Health checks ensure 99.9% uptime SLA."""
        # Step 1: Healthy services
        mock_redis_client.ping = AsyncMock(return_value=True)
        
        response = client.get("/health")
        assert response.status_code == 200
        
        health_data = response.json()
        assert health_data["status"] == "healthy"
        assert health_data["services"]["redis"] == "healthy"
        assert "timestamp" in health_data
        assert health_data["version"] == "0.1.0"
        
        # Step 2: Degraded service (Redis down)
        mock_redis_client.ping = AsyncMock(side_effect=Exception("Redis connection failed"))
        
        response = client.get("/health")
        assert response.status_code == 503
        
        health_data = response.json()
        assert health_data["status"] == "degraded"
        assert "unhealthy" in health_data["services"]["redis"]
    
    def test_user_flow_6_request_correlation_tracking(self, client):
        """User Flow 6: Request correlation IDs for distributed tracing."""
        # Step 1: Request without correlation ID (auto-generated)
        response = client.get("/")
        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
        assert "X-Response-Time" in response.headers
        assert "X-Request-ID" in response.headers
        
        # Step 2: Request with custom correlation ID
        custom_id = "test-correlation-123"
        headers = {"X-Correlation-ID": custom_id}
        response = client.get("/", headers=headers)
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == custom_id
    
    def test_user_flow_7_error_handling_with_correlation(self, client):
        """User Flow 7: Error handling includes correlation tracking."""
        # Step 1: Authentication error
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.get("/protected", headers=headers)
        assert response.status_code == 401
        
        error_data = response.json()
        assert "error" in error_data
        assert "correlation_id" in error_data["error"]
        assert "X-Correlation-ID" in response.headers
        
        # Step 2: Not found error
        response = client.get("/nonexistent")
        assert response.status_code == 404


class TestJWTServiceFunctionality:
    """Test JWT service functionality."""
    
    def test_jwt_token_creation_and_validation(self):
        """Test JWT token creation and validation."""
        # Create access token
        user_data = {"sub": "test_user", "role": "developer"}
        access_token = jwt_service.create_access_token(user_data)
        assert isinstance(access_token, str)
        assert len(access_token) > 0
        
        # Verify access token
        payload = jwt_service.verify_token(access_token, "access")
        assert payload["sub"] == "test_user"
        assert payload["type"] == "access"
        
        # Create refresh token
        refresh_token = jwt_service.create_refresh_token(user_data)
        assert isinstance(refresh_token, str)
        
        # Verify refresh token
        payload = jwt_service.verify_token(refresh_token, "refresh")
        assert payload["sub"] == "test_user"
        assert payload["type"] == "refresh"
    
    def test_jwt_token_type_validation(self):
        """Test JWT token type validation."""
        user_data = {"sub": "test_user"}
        access_token = jwt_service.create_access_token(user_data)
        
        # Should fail when using access token as refresh token
        with pytest.raises(Exception) as exc_info:
            jwt_service.verify_token(access_token, "refresh")
        assert "Invalid token type" in str(exc_info.value)


class TestPerformanceRequirements:
    """Test performance requirements."""
    
    def test_response_time_under_300ms(self, client):
        """Test p99 API response time < 300ms requirement."""
        response_times = []
        
        # Make multiple requests to measure response time
        for _ in range(10):
            start_time = time.time()
            response = client.get("/")
            end_time = time.time()
            
            assert response.status_code == 200
            response_time_ms = (end_time - start_time) * 1000
            response_times.append(response_time_ms)
        
        # Check p99 (in this case, max since we have few samples)
        max_response_time = max(response_times)
        assert max_response_time < 300, f"Response time {max_response_time}ms exceeds 300ms requirement"
        
        # Verify response time header is present
        response = client.get("/")
        assert "X-Response-Time" in response.headers


class TestSecurityRequirements:
    """Test security requirements."""
    
    def test_jwt_security_validation(self):
        """Test JWT security with proper algorithm."""
        # Verify JWT service uses HS256
        assert jwt_service.algorithm == "HS256"
        assert len(jwt_service.secret_key) >= 32  # Minimum secure length
    
    def test_cors_security_configuration(self, client):
        """Test CORS security configuration."""
        # Test allowed origin
        headers = {"Origin": "http://localhost:3000"}
        response = client.get("/", headers=headers)
        assert response.status_code == 200
        
        # CORS headers should be present for allowed origins
        assert "access-control-allow-origin" in response.headers
    
    def test_input_validation_security(self, client):
        """Test input validation for security."""
        # Test malformed JSON
        response = client.post("/auth/login", data="invalid-json")
        assert response.status_code == 422  # Validation error
        
        # Test missing required fields handled gracefully
        response = client.post("/auth/login", json={})
        assert response.status_code == 200  # Should handle gracefully with defaults


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
