"""
Simple Unit Tests for config.py - 80%+ Coverage Focus

Tests core functionality without complex environment variable parsing:
- Settings class initialization
- Basic field validation
- Core functionality coverage
"""

import pytest
from src.config import Settings, get_settings


class TestSettingsCore:
    """Test core Settings functionality."""
    
    def test_settings_initialization_defaults(self):
        """Test settings initialization with default values."""
        settings = Settings()
        
        assert settings.ENVIRONMENT == "development"
        assert settings.JWT_SECRET_KEY == "dev-secret-key-change-in-production"
        assert settings.DATABASE_URL == "postgresql+asyncpg://localhost/runlayer"
        assert settings.REDIS_URL == "redis://localhost:6379/0"
        assert isinstance(settings.CORS_ORIGINS, list)
        assert len(settings.CORS_ORIGINS) >= 1
        assert settings.RATE_LIMIT_REQUESTS == 1000
        assert settings.RATE_LIMIT_WINDOW == 3600
        assert settings.LOG_LEVEL == "INFO"
        assert settings.DB_POOL_SIZE == 20
        assert settings.DB_MAX_OVERFLOW == 30
    
    def test_settings_field_types(self):
        """Test settings field types are correct."""
        settings = Settings()
        
        assert isinstance(settings.ENVIRONMENT, str)
        assert isinstance(settings.JWT_SECRET_KEY, str)
        assert isinstance(settings.DATABASE_URL, str)
        assert isinstance(settings.REDIS_URL, str)
        assert isinstance(settings.CORS_ORIGINS, list)
        assert isinstance(settings.RATE_LIMIT_REQUESTS, int)
        assert isinstance(settings.RATE_LIMIT_WINDOW, int)
        assert isinstance(settings.LOG_LEVEL, str)
        assert isinstance(settings.DB_POOL_SIZE, int)
        assert isinstance(settings.DB_MAX_OVERFLOW, int)
    
    def test_cors_origins_validator_string_input(self):
        """Test CORS origins validator with string input."""
        # Test the validator function directly
        result = Settings.parse_cors_origins("http://localhost:3000,https://app.com")
        expected = ["http://localhost:3000", "https://app.com"]
        assert result == expected
    
    def test_cors_origins_validator_list_input(self):
        """Test CORS origins validator with list input."""
        input_list = ["http://localhost:3000", "https://app.com"]
        result = Settings.parse_cors_origins(input_list)
        assert result == input_list
    
    def test_cors_origins_validator_single_string(self):
        """Test CORS origins validator with single string."""
        result = Settings.parse_cors_origins("https://single-origin.com")
        assert result == ["https://single-origin.com"]
    
    def test_cors_origins_validator_with_spaces(self):
        """Test CORS origins validator handles spaces."""
        result = Settings.parse_cors_origins(" http://localhost:3000 , https://app.com ")
        expected = ["http://localhost:3000", "https://app.com"]
        assert result == expected
    
    def test_jwt_secret_validator(self):
        """Test JWT secret validator."""
        # Test the validator function directly
        result = Settings.validate_jwt_secret_production("test-secret-key", None)
        assert result == "test-secret-key"
    
    def test_database_url_validator(self):
        """Test database URL validator."""
        # Test the validator function directly
        result = Settings.validate_database_url_production("postgresql://test/db", None)
        assert result == "postgresql://test/db"


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
    
    def test_get_settings_has_all_required_fields(self):
        """Test get_settings instance has all required fields."""
        settings = get_settings()
        
        # Check all required fields exist
        required_fields = [
            'ENVIRONMENT', 'JWT_SECRET_KEY', 'CORS_ORIGINS', 'REDIS_URL',
            'DATABASE_URL', 'DB_POOL_SIZE', 'DB_MAX_OVERFLOW', 'DB_POOL_TIMEOUT',
            'DB_POOL_RECYCLE', 'RATE_LIMIT_REQUESTS', 'RATE_LIMIT_WINDOW', 'LOG_LEVEL'
        ]
        
        for field in required_fields:
            assert hasattr(settings, field), f"Missing field: {field}"
            assert getattr(settings, field) is not None, f"Field {field} is None"


class TestConfigurationValidation:
    """Test configuration validation."""
    
    def test_development_environment_defaults(self):
        """Test development environment has safe defaults."""
        settings = Settings()
        
        # Development should allow localhost
        assert "localhost" in settings.DATABASE_URL
        assert "localhost" in settings.REDIS_URL
        assert any("localhost" in origin for origin in settings.CORS_ORIGINS)
        
        # Should have reasonable defaults
        assert settings.RATE_LIMIT_REQUESTS > 0
        assert settings.DB_POOL_SIZE > 0
        assert len(settings.JWT_SECRET_KEY) >= 32
    
    def test_database_pool_configuration(self):
        """Test database pool configuration has reasonable values."""
        settings = Settings()
        
        assert settings.DB_POOL_SIZE > 0
        assert settings.DB_MAX_OVERFLOW > 0
        assert settings.DB_POOL_TIMEOUT > 0
        assert settings.DB_POOL_RECYCLE > 0
        
        # Pool overflow should be reasonable compared to base size
        assert settings.DB_MAX_OVERFLOW >= settings.DB_POOL_SIZE
    
    def test_rate_limiting_configuration(self):
        """Test rate limiting configuration."""
        settings = Settings()
        
        assert settings.RATE_LIMIT_REQUESTS > 0
        assert settings.RATE_LIMIT_WINDOW > 0
        
        # Window should be reasonable (not too short)
        assert settings.RATE_LIMIT_WINDOW >= 60  # At least 1 minute
    
    def test_cors_origins_not_empty(self):
        """Test CORS origins is not empty."""
        settings = Settings()
        
        assert len(settings.CORS_ORIGINS) > 0
        assert all(isinstance(origin, str) for origin in settings.CORS_ORIGINS)
        assert all(len(origin) > 0 for origin in settings.CORS_ORIGINS)


class TestConfigModel:
    """Test Pydantic model configuration."""
    
    def test_model_config_exists(self):
        """Test model configuration exists."""
        assert hasattr(Settings, 'model_config')
        config = Settings.model_config
        
        assert config['env_file'] == ".env"
        assert config['env_file_encoding'] == "utf-8"
        assert config['case_sensitive'] is True
    
    def test_field_validators_exist(self):
        """Test field validators are properly defined."""
        # Check that validators are defined
        assert hasattr(Settings, 'parse_cors_origins')
        assert hasattr(Settings, 'validate_jwt_secret_production')
        assert hasattr(Settings, 'validate_database_url_production')
        
        # Check they are callable
        assert callable(Settings.parse_cors_origins)
        assert callable(Settings.validate_jwt_secret_production)
        assert callable(Settings.validate_database_url_production)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src.config", "--cov-report=term-missing"])
