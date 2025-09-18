"""
12-Factor App configuration management for RunLayer SDK.

Following senior developer best practices:
- III. Config: Store config in environment variables
- Pydantic for validation and type safety
- Sensible defaults with environment override
- No secrets in code or config files
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseSettings, Field, validator
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


class RunLayerSettings(BaseSettings):
    """
    RunLayer SDK configuration using Pydantic BaseSettings.
    
    Follows 12-Factor App principle III: Config from environment.
    All configuration comes from environment variables with sensible defaults.
    """
    
    # Core settings
    api_key: Optional[str] = Field(None, env="RUNLAYER_API_KEY")
    api_base_url: str = Field("https://api.runlayer.com", env="RUNLAYER_API_BASE_URL")
    
    # Database settings (12-Factor App principle IV: Backing services)
    database_url: str = Field("sqlite:///runlayer.db", env="RUNLAYER_DATABASE_URL")
    database_pool_size: int = Field(10, env="RUNLAYER_DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(20, env="RUNLAYER_DATABASE_MAX_OVERFLOW")
    
    # Workspace settings
    default_workspace: str = Field("default", env="RUNLAYER_WORKSPACE")
    storage_path: Path = Field(Path.home() / ".runlayer", env="RUNLAYER_STORAGE_PATH")
    max_storage_mb: int = Field(100, env="RUNLAYER_MAX_STORAGE_MB")
    
    # Sync settings
    auto_sync: bool = Field(True, env="RUNLAYER_AUTO_SYNC")
    sync_interval_seconds: int = Field(300, env="RUNLAYER_SYNC_INTERVAL_SECONDS")
    batch_sync_size: int = Field(50, env="RUNLAYER_BATCH_SYNC_SIZE")
    
    # Performance settings
    max_proof_cache: int = Field(1000, env="RUNLAYER_MAX_PROOF_CACHE")
    request_timeout_seconds: int = Field(30, env="RUNLAYER_REQUEST_TIMEOUT_SECONDS")
    retry_attempts: int = Field(3, env="RUNLAYER_RETRY_ATTEMPTS")
    
    # Security settings
    encrypt_local_storage: bool = Field(True, env="RUNLAYER_ENCRYPT_LOCAL_STORAGE")
    verify_ssl: bool = Field(True, env="RUNLAYER_VERIFY_SSL")
    
    # Logging settings
    log_level: str = Field("INFO", env="RUNLAYER_LOG_LEVEL")
    log_format: str = Field("json", env="RUNLAYER_LOG_FORMAT")  # json or console
    enable_correlation_ids: bool = Field(True, env="RUNLAYER_ENABLE_CORRELATION_IDS")
    
    # Development settings
    debug: bool = Field(False, env="RUNLAYER_DEBUG")
    enable_sql_echo: bool = Field(False, env="RUNLAYER_ENABLE_SQL_ECHO")
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    @validator("storage_path", pre=True)
    def validate_storage_path(cls, v):
        """Convert string paths to Path objects."""
        if isinstance(v, str):
            return Path(v).expanduser()
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    @validator("log_format")
    def validate_log_format(cls, v):
        """Validate log format."""
        valid_formats = ["json", "console"]
        if v.lower() not in valid_formats:
            raise ValueError(f"Log format must be one of: {valid_formats}")
        return v.lower()
    
    def get_database_url(self, workspace_name: Optional[str] = None) -> str:
        """
        Get database URL for specific workspace.
        
        Supports workspace-specific databases for isolation.
        """
        if self.database_url.startswith("sqlite:///"):
            # For SQLite, create workspace-specific databases
            if workspace_name and workspace_name != "default":
                base_path = Path(self.database_url.replace("sqlite:///", ""))
                workspace_db = base_path.parent / f"{workspace_name}.db"
                return f"sqlite:///{workspace_db}"
        
        return self.database_url
    
    def get_workspace_storage_path(self, workspace_name: str) -> Path:
        """Get storage path for specific workspace."""
        return self.storage_path / workspace_name
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary (excluding sensitive data)."""
        data = self.dict()
        
        # Mask sensitive information
        if data.get("api_key"):
            data["api_key"] = "***masked***"
        
        # Convert Path objects to strings
        data["storage_path"] = str(data["storage_path"])
        
        return data


class ConfigManager:
    """
    Configuration manager following Singleton pattern.
    
    Provides centralized access to configuration throughout the application.
    """
    
    _instance: Optional['ConfigManager'] = None
    _settings: Optional[RunLayerSettings] = None
    
    def __new__(cls) -> 'ConfigManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @property
    def settings(self) -> RunLayerSettings:
        """Get current settings, loading them if necessary."""
        if self._settings is None:
            self._settings = RunLayerSettings()
        return self._settings
    
    def reload(self) -> None:
        """Reload settings from environment variables."""
        self._settings = RunLayerSettings()
    
    def update(self, **kwargs) -> None:
        """Update settings programmatically (for testing)."""
        if self._settings is None:
            self._settings = RunLayerSettings()
        
        for key, value in kwargs.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)


# Global configuration instance
config = ConfigManager()


def get_settings() -> RunLayerSettings:
    """
    Get current RunLayer settings.
    
    This is the main entry point for accessing configuration.
    """
    return config.settings


def create_env_file_template(path: Path = Path(".env.example")) -> None:
    """
    Create a template .env file with all available configuration options.
    
    Useful for development and deployment setup.
    """
    template = """# RunLayer SDK Configuration
# Copy this file to .env and customize for your environment

# API Configuration
RUNLAYER_API_KEY=your-api-key-here
RUNLAYER_API_BASE_URL=https://api.runlayer.com

# Database Configuration (12-Factor App principle IV)
RUNLAYER_DATABASE_URL=sqlite:///runlayer.db
# For PostgreSQL: postgresql://user:password@localhost/runlayer
# For MySQL: mysql://user:password@localhost/runlayer

# Workspace Configuration
RUNLAYER_WORKSPACE=default
RUNLAYER_STORAGE_PATH=~/.runlayer
RUNLAYER_MAX_STORAGE_MB=100

# Sync Configuration
RUNLAYER_AUTO_SYNC=true
RUNLAYER_SYNC_INTERVAL_SECONDS=300
RUNLAYER_BATCH_SYNC_SIZE=50

# Performance Configuration
RUNLAYER_MAX_PROOF_CACHE=1000
RUNLAYER_REQUEST_TIMEOUT_SECONDS=30
RUNLAYER_RETRY_ATTEMPTS=3

# Security Configuration
RUNLAYER_ENCRYPT_LOCAL_STORAGE=true
RUNLAYER_VERIFY_SSL=true

# Logging Configuration
RUNLAYER_LOG_LEVEL=INFO
RUNLAYER_LOG_FORMAT=json
RUNLAYER_ENABLE_CORRELATION_IDS=true

# Development Configuration
RUNLAYER_DEBUG=false
RUNLAYER_ENABLE_SQL_ECHO=false
"""
    
    path.write_text(template)
    print(f"Environment template created at {path}")


if __name__ == "__main__":
    # Create example .env file when run directly
    create_env_file_template()
