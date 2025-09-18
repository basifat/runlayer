"""
Validator Executor - Story 7: Basic Validator Framework

Orchestrates validator execution with Redis job queue integration.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, AsyncGenerator
import uuid

from ..redis import validator_queue, validator_cache
from .interface import (
    ValidatorInterface, 
    ValidatorResult, 
    ValidationStatus, 
    ValidationError,
    ValidatorConfig
)

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """Context for validator execution."""
    
    # Request metadata
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    workspace_id: Optional[str] = None
    
    # Execution settings
    priority: int = 1  # 1=high, 2=normal, 3=low
    async_execution: bool = False
    cache_results: bool = True
    cache_ttl_seconds: int = 300  # 5 minutes
    
    # Tracing and monitoring
    correlation_id: Optional[str] = None
    parent_execution_id: Optional[str] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "priority": self.priority,
            "async_execution": self.async_execution,
            "cache_results": self.cache_results,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "correlation_id": self.correlation_id,
            "parent_execution_id": self.parent_execution_id,
            "metadata": self.metadata
        }


class ValidatorExecutor:
    """
    Orchestrates validator execution with Redis integration.
    
    Features:
    - Async/sync execution modes
    - Redis job queue integration
    - Result caching
    - Error handling and retries
    - Performance monitoring
    """
    
    def __init__(self):
        self.active_executions: Dict[str, ValidatorResult] = {}
        self.execution_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "average_execution_time_ms": 0.0
        }
    
    async def execute_validator(
        self,
        validator: ValidatorInterface,
        input_data: Dict[str, Any],
        context: Optional[ExecutionContext] = None
    ) -> ValidatorResult:
        """
        Execute validator with full orchestration.
        
        Args:
            validator: The validator to execute
            input_data: Input data for validation
            context: Execution context
            
        Returns:
            ValidatorResult with execution details
        """
        context = context or ExecutionContext()
        
        # Check cache first
        if context.cache_results:
            cached_result = await self._get_cached_result(
                validator.validator_id, 
                input_data
            )
            if cached_result:
                logger.info(f"Cache hit for validator {validator.validator_id}")
                return cached_result
        
        # Execute based on mode
        if context.async_execution:
            return await self._execute_async(validator, input_data, context)
        else:
            return await self._execute_sync(validator, input_data, context)
    
    async def _execute_sync(
        self,
        validator: ValidatorInterface,
        input_data: Dict[str, Any],
        context: ExecutionContext
    ) -> ValidatorResult:
        """Execute validator synchronously."""
        result = ValidatorResult(
            validator_id=validator.validator_id,
            status=ValidationStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        
        self.active_executions[result.execution_id] = result
        
        try:
            # Execute with timeout
            start_time = time.time()
            
            async with self._execution_timeout(validator.config.timeout_seconds):
                result = await validator.validate(input_data, context.to_dict())
            
            # Update timing
            end_time = time.time()
            result.execution_time_ms = int((end_time - start_time) * 1000)
            result.completed_at = datetime.utcnow()
            result.status = ValidationStatus.COMPLETED
            
            # Cache result if enabled
            if context.cache_results:
                await self._cache_result(
                    validator.validator_id,
                    input_data,
                    result,
                    context.cache_ttl_seconds
                )
            
            # Update stats
            self._update_stats(result)
            
            logger.info(
                f"Validator {validator.validator_id} completed successfully "
                f"in {result.execution_time_ms}ms"
            )
            
            return result
            
        except asyncio.TimeoutError:
            result.status = ValidationStatus.TIMEOUT
            result.error = ValidationError(
                code="EXECUTION_TIMEOUT",
                message=f"Validator execution exceeded {validator.config.timeout_seconds}s timeout"
            )
            result.completed_at = datetime.utcnow()
            
            logger.warning(f"Validator {validator.validator_id} timed out")
            self._update_stats(result)
            return result
            
        except Exception as e:
            result.status = ValidationStatus.FAILED
            result.error = ValidationError(
                code="EXECUTION_ERROR",
                message=str(e),
                details={"exception_type": type(e).__name__}
            )
            result.completed_at = datetime.utcnow()
            
            logger.error(
                f"Validator {validator.validator_id} failed: {e}",
                exc_info=True
            )
            self._update_stats(result)
            return result
            
        finally:
            # Cleanup
            self.active_executions.pop(result.execution_id, None)
    
    async def _execute_async(
        self,
        validator: ValidatorInterface,
        input_data: Dict[str, Any],
        context: ExecutionContext
    ) -> ValidatorResult:
        """Execute validator asynchronously via Redis job queue."""
        
        # Create job payload
        job_payload = {
            "validator_id": validator.validator_id,
            "input_data": input_data,
            "context": context.to_dict(),
            "validator_metadata": validator.get_metadata()
        }
        
        # Enqueue job
        job_id = await validator_queue.enqueue(
            "execute_validator",
            job_payload,
            priority=context.priority
        )
        
        # Return pending result with job ID
        result = ValidatorResult(
            execution_id=job_id,
            validator_id=validator.validator_id,
            status=ValidationStatus.PENDING,
            started_at=datetime.utcnow(),
            metadata={"job_id": job_id, "async_execution": True}
        )
        
        logger.info(f"Queued async execution for validator {validator.validator_id}, job_id: {job_id}")
        return result
    
    async def get_execution_status(self, execution_id: str) -> Optional[ValidatorResult]:
        """Get status of an execution."""
        
        # Check active executions first
        if execution_id in self.active_executions:
            return self.active_executions[execution_id]
        
        # Check Redis job status for async executions
        try:
            job = await validator_queue.get_job_status(execution_id)
            if job:
                # Convert job status to ValidatorResult
                result = ValidatorResult(
                    execution_id=execution_id,
                    status=ValidationStatus(job.status),
                    started_at=job.created_at,
                    completed_at=job.completed_at,
                    metadata={"job_id": execution_id, "async_execution": True}
                )
                
                if job.result:
                    # Parse job result back to ValidatorResult
                    result.is_valid = job.result.get("is_valid")
                    result.confidence_score = job.result.get("confidence_score")
                    result.output_data = job.result.get("output_data")
                    result.execution_time_ms = job.result.get("execution_time_ms", 0)
                
                return result
                
        except Exception as e:
            logger.error(f"Error getting job status for {execution_id}: {e}")
        
        return None
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an execution."""
        
        # Cancel active execution
        if execution_id in self.active_executions:
            result = self.active_executions[execution_id]
            result.status = ValidationStatus.CANCELLED
            result.completed_at = datetime.utcnow()
            self.active_executions.pop(execution_id)
            return True
        
        # Cancel Redis job
        try:
            return await validator_queue.cancel_job(execution_id)
        except Exception as e:
            logger.error(f"Error cancelling job {execution_id}: {e}")
            return False
    
    async def _get_cached_result(
        self, 
        validator_id: str, 
        input_data: Dict[str, Any]
    ) -> Optional[ValidatorResult]:
        """Get cached validation result."""
        try:
            cache_key = self._generate_cache_key(validator_id, input_data)
            cached_data = await validator_cache.get(cache_key)
            
            if cached_data:
                # Reconstruct ValidatorResult from cached data
                result = ValidatorResult(**cached_data)
                result.metadata["cache_hit"] = True
                return result
                
        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
        
        return None
    
    async def _cache_result(
        self,
        validator_id: str,
        input_data: Dict[str, Any],
        result: ValidatorResult,
        ttl_seconds: int
    ) -> None:
        """Cache validation result."""
        try:
            cache_key = self._generate_cache_key(validator_id, input_data)
            await validator_cache.set(
                cache_key,
                result.to_dict(),
                ttl=ttl_seconds
            )
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")
    
    def _generate_cache_key(self, validator_id: str, input_data: Dict[str, Any]) -> str:
        """Generate cache key for validator execution."""
        import hashlib
        import json
        
        # Create deterministic hash of input data
        input_hash = hashlib.sha256(
            json.dumps(input_data, sort_keys=True).encode()
        ).hexdigest()[:16]
        
        return f"validator:{validator_id}:input:{input_hash}"
    
    @asynccontextmanager
    async def _execution_timeout(self, timeout_seconds: int) -> AsyncGenerator[None, None]:
        """Context manager for execution timeout."""
        try:
            async with asyncio.timeout(timeout_seconds):
                yield
        except asyncio.TimeoutError:
            raise
    
    def _update_stats(self, result: ValidatorResult) -> None:
        """Update execution statistics."""
        self.execution_stats["total_executions"] += 1
        
        if result.is_successful:
            self.execution_stats["successful_executions"] += 1
        else:
            self.execution_stats["failed_executions"] += 1
        
        # Update average execution time
        if result.execution_time_ms > 0:
            total = self.execution_stats["total_executions"]
            current_avg = self.execution_stats["average_execution_time_ms"]
            new_avg = ((current_avg * (total - 1)) + result.execution_time_ms) / total
            self.execution_stats["average_execution_time_ms"] = new_avg
    
    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        return {
            **self.execution_stats,
            "active_executions": len(self.active_executions),
            "success_rate": (
                self.execution_stats["successful_executions"] / 
                max(1, self.execution_stats["total_executions"])
            ) * 100
        }


# Global executor instance
validator_executor = ValidatorExecutor()
