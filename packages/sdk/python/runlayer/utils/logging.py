"""
Structured Logging for RunLayer SDK

Provides consistent, structured logging throughout the SDK with:
- Correlation IDs for request tracing
- JSON formatting for production
- Configurable log levels
- Performance metrics
"""

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional
import structlog
from structlog.stdlib import LoggerFactory


# Context variable for correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


def add_correlation_id(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add correlation ID to log events."""
    corr_id = correlation_id.get()
    if corr_id:
        event_dict['correlation_id'] = corr_id
    return event_dict


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    include_timestamp: bool = True
) -> None:
    """
    Setup structured logging for the RunLayer SDK.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON formatting for logs
        include_timestamp: Include timestamps in logs
    """
    # Configure structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        add_correlation_id,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if include_timestamp:
        processors.append(structlog.processors.TimeStamper(fmt="ISO"))
    
    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper())
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured structured logger
    """
    return structlog.get_logger(name)


def set_correlation_id(corr_id: Optional[str] = None) -> str:
    """
    Set correlation ID for request tracing.
    
    Args:
        corr_id: Correlation ID (generates one if None)
        
    Returns:
        The correlation ID that was set
    """
    if corr_id is None:
        corr_id = str(uuid.uuid4())[:8]
    
    correlation_id.set(corr_id)
    return corr_id


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id.get()


class PerformanceLogger:
    """Context manager for logging performance metrics."""
    
    def __init__(self, logger: structlog.stdlib.BoundLogger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        import time
        self.start_time = time.perf_counter()
        self.logger.debug("Operation started", operation=self.operation)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        if self.start_time:
            duration_ms = (time.perf_counter() - self.start_time) * 1000
            
            if exc_type:
                self.logger.error(
                    "Operation failed",
                    operation=self.operation,
                    duration_ms=round(duration_ms, 2),
                    error=str(exc_val)
                )
            else:
                self.logger.info(
                    "Operation completed",
                    operation=self.operation,
                    duration_ms=round(duration_ms, 2)
                )


# Initialize default logging
setup_logging()

# Default logger for the SDK
sdk_logger = get_logger("runlayer.sdk")
