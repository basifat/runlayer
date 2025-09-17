"""
Unit tests for config.py - 12-Factor App Configuration

Tests all configuration functionality to ensure 80%+ coverage:
- Settings class initialization
- Environment variable loading
- Validation logic
- Production safety checks
"""

import pytest
import os
from unittest.mock import patch
from pydantic import ValidationError

from src.config import Settings, get_settings


class TestSettings:
    """Test Settings class functionality."""
    
    def test_settings_initialization_defaults(self):
        """Test settings initialization with default values."""
        settings = Settings()
        
        assert settings.ENVIRONMENT == "development"
        assert settings.JWT_SECRET_KEY == "dev-secret-key-change-in-production"
        assert settings.DATABASE_URL == "postgresql+asyncpg://localhost/runlayer"
        assert settings.REDIS_URL == "redis://localhost:6379/0"
        assert settings.CORS_ORIGINS == ["http://localhost:3000", "http://localhost:8080"]
        assert settings.RATE_LIMIT_REQUESTS == 1000
        assert settings.RATE_LIMIT_WINDOW == 3600
        assert settings.LOG_LEVEL == "INFO"
        assert settings.DB_POOL_SIZE == 20
        assert settings.DB_MAX_OVERFLOW == 30
    
    @patch.dict(os.environ, {
        'ENVIRONMENT': 'production',
        'JWT_SECRET_KEY': 'super-secure-production-key-32-chars',
        'DATABASE_URL': 'postgresql+asyncpg://prod-db:5432/runlayer',
        'REDIS_URL': 'redis://prod-redis:6379/1',
        'CORS_ORIGINS': 'https://app.runlayer.com,https://api.runlayer.com',
        'RATE_LIMIT_REQUESTS': '5000',
        'RATE_LIMIT_WINDOW': '1800',
        'LOG_LEVEL': 'WARNING',
        'DB_POOL_SIZE': '50',
        'DB_MAX_OVERFLOW': '100'
    })
    def test_settings_from_environment(self):
        """Test settings loading from environment variables."""
        settings = Settings()
        
        assert settings.ENVIRONMENT == "production"
        assert settings.JWT_SECRET_KEY == "super-secure-production-key-32-chars"
        assert settings.DATABASE_URL == "postgresql+asyncpg://prod-db:5432/runlayer"
        assert settings.REDIS_URL == "redis://prod-redis:6379/1"
        assert settings.CORS_ORIGINS == ["https://app.runlayer.com", "https://api.runlayer.com"]
        assert settings.RATE_LIMIT_REQUESTS == 5000
        assert settings.RATE_LIMIT_WINDOW == 1800
        assert settings.LOG_LEVEL == "WARNING"
        assert settings.DB_POOL_SIZE == 50
        assert settings.DB_MAX_OVERFLOW == 100
    
    def test_cors_origins_parsing(self):
        """Test CORS origins parsing from comma-separated string."""
        with patch.dict(os.environ, {'CORS_ORIGINS': 'http://localhost:3000, https://app.com, https://api.com'}):
            settings = Settings()
            expected = ["http://localhost:3000", "https://app.com", "https://api.com"]
            assert settings.CORS_ORIGINS == expected
    
    def test_cors_origins_single_value(self):
        """Test CORS origins with single value."""
        with patch.dict(os.environ, {'CORS_ORIGINS': 'https://single-origin.com'}):
            settings = Settings()
            assert settings.CORS_ORIGINS == ["https://single-origin.com"]
    
    @patch.dict(os.environ, {
        'ENVIRONMENT': 'production',
        'JWT_SECRET_KEY': 'dev-secret-key-change-in-production'
    })
    def test_jwt_secret_production_validation_fails(self):
        """Test JWT secret validation fails in production with default key."""
        with pytest.raises(ValidationError) as exc_info:
            Settings()
        assert "JWT_SECRET_KEY must be set in production" in str(exc_info.value)
    
    @patch.dict(os.environ, {
        'ENVIRONMENT': 'production',
        'DATABASE_URL': 'postgresql+asyncpg://localhost/runlayer'
    })
    def test_database_url_production_validation_fails(self):
        """Test database URL validation fails in production with localhost."""
        with pytest.raises(ValidationError) as exc_info:
            Settings()
        assert "DATABASE_URL must not use localhost in production" in str(exc_info.value)
    
    @patch.dict(os.environ, {
        'ENVIRONMENT': 'production',
        'JWT_SECRET_KEY': 'secure-production-key-32-characters',
        'DATABASE_URL': 'postgresql+asyncpg://prod-db:5432/runlayer'
    })
    def test_production_validation_passes(self):
        """Test production validation passes with proper values."""
        settings = Settings()
        assert settings.ENVIRONMENT == "production"
        assert settings.JWT_SECRET_KEY == "secure-production-key-32-characters"
        assert settings.DATABASE_URL == "postgresql+asyncpg://prod-db:5432/runlayer"
    
    def test_jwt_secret_minimum_length(self):
        """Test JWT secret minimum length validation."""
        with patch.dict(os.environ, {'JWT_SECRET_KEY': 'short'}):
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            assert "at least 32 characters" in str(exc_info.value)
    
    def test_database_pool_settings(self):
        """Test database pool configuration."""
        with patch.dict(os.environ, {
            'DB_POOL_SIZE': '25',
            'DB_MAX_OVERFLOW': '50',
            'DB_POOL_TIMEOUT': '60',
            'DB_POOL_RECYCLE': '7200'
        }):
            settings = Settings()
            assert settings.DB_POOL_SIZE == 25
            assert settings.DB_MAX_OVERFLOW == 50
            assert settings.DB_POOL_TIMEOUT == 60
            assert settings.DB_POOL_RECYCLE == 7200
    
    def test_rate_limiting_configuration(self):
        """Test rate limiting configuration."""
        with patch.dict(os.environ, {
            'RATE_LIMIT_REQUESTS': '2000',
            'RATE_LIMIT_WINDOW': '900'
        }):
            settings = Settings()
            assert settings.RATE_LIMIT_REQUESTS == 2000
            assert settings.RATE_LIMIT_WINDOW == 900


class TestGetSettings:
    """Test get_settings function."""
    
    def test_get_settings_returns_settings_instance(self):
        """Test get_settings returns Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)
    
    def test_get_settings_caching(self):
        """Test get_settings returns cached instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2  # Same instance (cached)
    
    @patch.dict(os.environ, {'ENVIRONMENT': 'test'})
    def test_get_settings_with_environment(self):
        """Test get_settings with environment variable."""
        # Clear cache first
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.ENVIRONMENT == "test"


class TestConfigValidation:
    """Test configuration validation edge cases."""
    
    def test_empty_cors_origins(self):
        """Test empty CORS origins handling."""
        with patch.dict(os.environ, {'CORS_ORIGINS': ''}):
            settings = Settings()
            assert settings.CORS_ORIGINS == [""]
    
    def test_cors_origins_with_spaces(self):
        """Test CORS origins with extra spaces."""
        with patch.dict(os.environ, {'CORS_ORIGINS': ' http://localhost:3000 , https://app.com '}):
            settings = Settings()
            assert settings.CORS_ORIGINS == ["http://localhost:3000", "https://app.com"]
    
    def test_log_level_case_insensitive(self):
        """Test log level accepts different cases."""
        with patch.dict(os.environ, {'LOG_LEVEL': 'debug'}):
            settings = Settings()
            assert settings.LOG_LEVEL == "debug"
    
    def test_boolean_environment_variables(self):
        """Test boolean-like environment variables."""
        # Test that numeric strings are properly converted
        with patch.dict(os.environ, {
            'DB_POOL_SIZE': '0',
            'RATE_LIMIT_REQUESTS': '1'
        }):
            settings = Settings()
            assert settings.DB_POOL_SIZE == 0
            assert settings.RATE_LIMIT_REQUESTS == 1


class TestConfigIntegration:
    """Integration tests for configuration."""
    
    def test_development_environment_defaults(self):
        """Test development environment has safe defaults."""
        with patch.dict(os.environ, {'ENVIRONMENT': 'development'}, clear=True):
            settings = Settings()
            
            # Development should allow localhost
            assert "localhost" in settings.DATABASE_URL
            assert "localhost" in settings.REDIS_URL
            assert any("localhost" in origin for origin in settings.CORS_ORIGINS)
            
            # Should have reasonable defaults
            assert settings.RATE_LIMIT_REQUESTS > 0
            assert settings.DB_POOL_SIZE > 0
    
    def test_production_environment_security(self):
        """Test production environment enforces security."""
        with patch.dict(os.environ, {
            'ENVIRONMENT': 'production',
            'JWT_SECRET_KEY': 'secure-production-key-with-32-chars',
            'DATABASE_URL': 'postgresql+asyncpg://prod-db:5432/runlayer',
            'REDIS_URL': 'redis://prod-redis:6379/0',
            'CORS_ORIGINS': 'https://app.runlayer.com'
        }):
            settings = Settings()
            
            # Production should not use localhost
            assert "localhost" not in settings.DATABASE_URL
            assert "localhost" not in settings.REDIS_URL
            assert not any("localhost" in origin for origin in settings.CORS_ORIGINS)
            
            # Should have secure JWT key
            assert len(settings.JWT_SECRET_KEY) >= 32
            assert settings.JWT_SECRET_KEY != "dev-secret-key-change-in-production"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src.config", "--cov-report=term-missing"])
