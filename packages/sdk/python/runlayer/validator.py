"""
@validator Decorator

The core decorator that transforms any Python function into a validated function.
This is the key feature that makes RunLayer "Temporal for AI Validation" - 
as simple as adding @validator to any function.

Usage:
    @validator(name="email_validation", version="1.0.0")
    def validate_email(email: str) -> bool:
        return "@" in email
    
    # Function now automatically creates proofs
    result = validate_email("test@example.com")
"""

import functools
import time
from typing import Any, Callable, Optional, TypeVar, Union
from datetime import datetime

from .client import RunLayerClient
from .models.proof import RunProof
from .utils.logging import get_logger, PerformanceLogger, set_correlation_id

logger = get_logger(__name__)

# Type variable for decorated function
F = TypeVar('F', bound=Callable[..., Any])


class ValidatorConfig:
    """Configuration for a validator function."""
    
    def __init__(
        self,
        name: str,
        version: str,
        client: Optional[RunLayerClient] = None,
        cache_results: bool = True,
        auto_sign: bool = True,
        description: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        self.name = name
        self.version = version
        self.client = client
        self.cache_results = cache_results
        self.auto_sign = auto_sign
        self.description = description
        self.metadata = metadata or {}


def validator(
    name: str,
    version: str,
    client: Optional[RunLayerClient] = None,
    cache_results: bool = True,
    auto_sign: bool = True,
    description: Optional[str] = None,
    metadata: Optional[dict] = None
) -> Callable[[F], F]:
    """
    Decorator that transforms any function into a validated function.
    
    The decorated function will:
    1. Execute the original function
    2. Create a RunProof with input/output hashes
    3. Store the proof locally (and sync to cloud if configured)
    4. Return the original result
    
    Args:
        name: Validator name (should be unique and descriptive)
        version: Semantic version (e.g., "1.0.0")
        client: RunLayer client (uses default if None)
        cache_results: Return cached result for same input (default: True)
        auto_sign: Automatically sign proofs with Ed25519 (default: True)
        description: Optional description of the validator
        metadata: Additional metadata to include in proofs
        
    Returns:
        Decorated function that creates proofs automatically
        
    Example:
        @validator(name="email_validation", version="1.0.0")
        def validate_email(email: str) -> bool:
            import re
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
            return bool(re.match(pattern, email))
        
        # Usage automatically creates and stores proofs
        result = validate_email("test@example.com")  # Returns bool + creates proof
    """
    
    def decorator(func: F) -> F:
        # Create validator configuration
        config = ValidatorConfig(
            name=name,
            version=version,
            client=client,
            cache_results=cache_results,
            auto_sign=auto_sign,
            description=description,
            metadata=metadata
        )
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Set correlation ID for tracing
            correlation_id = set_correlation_id()
            
            # Get client (use provided or default)
            client_instance = config.client
            if client_instance is None:
                from . import get_default_client
                client_instance = get_default_client()
            
            # Prepare input data for hashing
            input_data = {
                "args": args,
                "kwargs": kwargs
            }
            
            # Generate input hash
            input_hash = RunProof._hash_data(input_data)
            
            # Check for cached result if enabled
            if config.cache_results:
                existing_proof = client_instance.find_existing_proof(
                    config.name, config.version, input_hash
                )
                
                if existing_proof:
                    logger.debug("Using cached result",
                               validator=config.name,
                               version=config.version,
                               proof_id=existing_proof.id,
                               correlation_id=correlation_id)
                    return existing_proof.output_data
            
            # Execute the original function with performance tracking
            with PerformanceLogger(logger, f"validator_execution_{config.name}"):
                start_time = time.perf_counter()
                
                try:
                    result = func(*args, **kwargs)
                    execution_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
                    
                    logger.debug("Validator executed successfully",
                               validator=config.name,
                               version=config.version,
                               execution_time_ms=execution_time_ms,
                               correlation_id=correlation_id)
                    
                except Exception as e:
                    execution_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
                    
                    logger.error("Validator execution failed",
                               validator=config.name,
                               version=config.version,
                               execution_time_ms=execution_time_ms,
                               error=str(e),
                               correlation_id=correlation_id)
                    
                    # Create proof for failed execution
                    _create_failure_proof(
                        config, client_instance, input_data, str(e), 
                        execution_time_ms, correlation_id
                    )
                    
                    # Re-raise the original exception
                    raise
            
            # Create and store proof
            try:
                proof = RunProof.create_proof(
                    validator_name=config.name,
                    validator_version=config.version,
                    input_data=input_data,
                    output_data=result,
                    execution_time_ms=execution_time_ms,
                    workspace_id=client_instance.workspace.id,
                    metadata={
                        **config.metadata,
                        "correlation_id": correlation_id,
                        "function_name": func.__name__,
                        "function_module": func.__module__,
                        "description": config.description
                    }
                )
                
                # Store proof (includes signing if auto_sign is True)
                success = client_instance.store_proof(proof, sign=config.auto_sign)
                
                if success:
                    logger.info("Proof created and stored",
                              validator=config.name,
                              version=config.version,
                              proof_id=proof.id,
                              correlation_id=correlation_id)
                else:
                    logger.warning("Failed to store proof",
                                 validator=config.name,
                                 version=config.version,
                                 correlation_id=correlation_id)
                
            except Exception as e:
                logger.error("Failed to create proof",
                           validator=config.name,
                           version=config.version,
                           error=str(e),
                           correlation_id=correlation_id)
                # Don't fail the original function call due to proof creation errors
            
            return result
        
        # Add metadata to the wrapped function
        wrapper._runlayer_validator = config
        wrapper._runlayer_original_func = func
        
        return wrapper
    
    return decorator


def _create_failure_proof(
    config: ValidatorConfig,
    client: RunLayerClient,
    input_data: dict,
    error_message: str,
    execution_time_ms: int,
    correlation_id: str
) -> None:
    """Create a proof for failed validator execution."""
    try:
        failure_proof = RunProof.create_proof(
            validator_name=config.name,
            validator_version=config.version,
            input_data=input_data,
            output_data={"error": error_message, "success": False},
            execution_time_ms=execution_time_ms,
            workspace_id=client.workspace.id,
            metadata={
                **config.metadata,
                "correlation_id": correlation_id,
                "execution_status": "failed",
                "error_message": error_message
            }
        )
        
        failure_proof.mark_failed()
        client.store_proof(failure_proof, sign=config.auto_sign)
        
        logger.debug("Failure proof created", proof_id=failure_proof.id)
        
    except Exception as e:
        logger.error("Failed to create failure proof", error=str(e))


def get_validator_info(func: Callable) -> Optional[ValidatorConfig]:
    """
    Get validator configuration from a decorated function.
    
    Args:
        func: Decorated function
        
    Returns:
        ValidatorConfig if function is decorated, None otherwise
    """
    return getattr(func, '_runlayer_validator', None)


def is_validator(func: Callable) -> bool:
    """
    Check if a function is decorated with @validator.
    
    Args:
        func: Function to check
        
    Returns:
        True if function is a validator
    """
    return hasattr(func, '_runlayer_validator')


def get_original_function(func: Callable) -> Optional[Callable]:
    """
    Get the original undecorated function.
    
    Args:
        func: Decorated function
        
    Returns:
        Original function if available, None otherwise
    """
    return getattr(func, '_runlayer_original_func', None)


# Convenience function for creating validators programmatically
def create_validator(
    func: Callable,
    name: str,
    version: str,
    **kwargs
) -> Callable:
    """
    Create a validator from an existing function programmatically.
    
    Args:
        func: Function to decorate
        name: Validator name
        version: Validator version
        **kwargs: Additional validator configuration
        
    Returns:
        Decorated validator function
        
    Example:
        def my_function(x: int) -> bool:
            return x > 0
        
        validator_func = create_validator(
            my_function,
            name="positive_check",
            version="1.0.0"
        )
    """
    return validator(name=name, version=version, **kwargs)(func)
