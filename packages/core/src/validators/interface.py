"""
Validator Interface Definition - Story 7: Basic Validator Framework

Defines the core interfaces for validator execution following senior engineer patterns.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import uuid


class ValidationStatus(str, Enum):
    """Validation execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ValidatorType(str, Enum):
    """Supported validator types."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    WASM = "wasm"
    DOCKER = "docker"


@dataclass
class ValidationError:
    """Structured validation error information."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    traceback: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "traceback": self.traceback
        }


@dataclass
class ValidatorResult:
    """Result of validator execution."""
    
    # Execution metadata
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    validator_id: str = ""
    status: ValidationStatus = ValidationStatus.PENDING
    
    # Timing information
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: int = 0
    
    # Validation results
    is_valid: Optional[bool] = None
    confidence_score: Optional[float] = None
    output_data: Optional[Dict[str, Any]] = None
    
    # Error handling
    error: Optional[ValidationError] = None
    
    # Resource usage
    memory_usage_mb: Optional[float] = None
    cpu_time_ms: Optional[int] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Calculate execution duration."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
    
    @property
    def is_successful(self) -> bool:
        """Check if validation completed successfully."""
        return self.status == ValidationStatus.COMPLETED and self.error is None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "execution_id": self.execution_id,
            "validator_id": self.validator_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "is_valid": self.is_valid,
            "confidence_score": self.confidence_score,
            "output_data": self.output_data,
            "error": self.error.to_dict() if self.error else None,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_time_ms": self.cpu_time_ms,
            "metadata": self.metadata
        }


@dataclass
class ValidatorConfig:
    """Configuration for validator execution."""
    
    # Resource limits (Story 7 requirements)
    timeout_seconds: int = 30  # 30 second limit
    memory_limit_mb: int = 512  # 512MB memory limit
    cpu_limit_percent: float = 100.0
    
    # Execution environment
    allow_network: bool = False
    allow_filesystem: bool = False
    environment_variables: Dict[str, str] = field(default_factory=dict)
    
    # Security settings
    sandbox_enabled: bool = True
    readonly_mode: bool = True
    
    # Retry configuration
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timeout_seconds": self.timeout_seconds,
            "memory_limit_mb": self.memory_limit_mb,
            "cpu_limit_percent": self.cpu_limit_percent,
            "allow_network": self.allow_network,
            "allow_filesystem": self.allow_filesystem,
            "environment_variables": self.environment_variables,
            "sandbox_enabled": self.sandbox_enabled,
            "readonly_mode": self.readonly_mode,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds
        }


class ValidatorInterface(ABC):
    """Abstract interface for all validator types."""
    
    def __init__(self, validator_id: str, config: Optional[ValidatorConfig] = None):
        self.validator_id = validator_id
        self.config = config or ValidatorConfig()
        self.validator_type = self._get_validator_type()
    
    @abstractmethod
    def _get_validator_type(self) -> ValidatorType:
        """Return the validator type."""
        pass
    
    @abstractmethod
    async def validate(
        self, 
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidatorResult:
        """
        Execute validation on input data.
        
        Args:
            input_data: The data to validate
            context: Optional execution context
            
        Returns:
            ValidatorResult with execution details
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if validator is healthy and ready for execution."""
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get validator metadata."""
        return {
            "validator_id": self.validator_id,
            "validator_type": self.validator_type.value,
            "config": self.config.to_dict()
        }


class ValidatorFactory(ABC):
    """Abstract factory for creating validators."""
    
    @abstractmethod
    def create_validator(
        self, 
        validator_id: str,
        validator_code: str,
        config: Optional[ValidatorConfig] = None
    ) -> ValidatorInterface:
        """Create a validator instance."""
        pass
    
    @abstractmethod
    def supports_type(self, validator_type: ValidatorType) -> bool:
        """Check if factory supports the given validator type."""
        pass
