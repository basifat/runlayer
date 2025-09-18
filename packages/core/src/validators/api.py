"""
Validator API Endpoints - Story 7: Basic Validator Framework

FastAPI endpoints for validator management and execution.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import logging

from .interface import ValidatorType, ValidatorConfig
from .executor import validator_executor, ExecutionContext
from .registry import validator_registry

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/validators", tags=["validators"])


# Pydantic models for API
class ValidatorCreateRequest(BaseModel):
    """Request model for creating validators."""
    validator_type: ValidatorType
    validator_code: str = Field(..., min_length=1, max_length=50000)
    validator_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    
    class Config:
        schema_extra = {
            "example": {
                "validator_type": "python",
                "validator_code": "result = input_data.get('text', '').strip() != ''",
                "validator_id": "text_not_empty",
                "config": {
                    "timeout_seconds": 30,
                    "memory_limit_mb": 512
                }
            }
        }


class ValidatorExecuteRequest(BaseModel):
    """Request model for validator execution."""
    input_data: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None
    async_execution: bool = False
    cache_results: bool = True
    
    class Config:
        schema_extra = {
            "example": {
                "input_data": {
                    "text": "Hello, world!",
                    "metadata": {"source": "user_input"}
                },
                "context": {
                    "user_id": "user123",
                    "workspace_id": "workspace456"
                },
                "async_execution": False,
                "cache_results": True
            }
        }


class ValidatorResponse(BaseModel):
    """Response model for validator operations."""
    validator_id: str
    validator_type: str
    created_at: Optional[datetime] = None
    config: Dict[str, Any]
    healthy: bool = True


class ExecutionResponse(BaseModel):
    """Response model for validator execution."""
    execution_id: str
    validator_id: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: int = 0
    is_valid: Optional[bool] = None
    confidence_score: Optional[float] = None
    output_data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = {}


# API Endpoints

@router.post("/", response_model=ValidatorResponse)
async def create_validator(request: ValidatorCreateRequest):
    """
    Create a new validator.
    
    Creates and registers a validator with the specified type and code.
    Supports Python validators with sandboxing and security controls.
    """
    try:
        # Parse config if provided
        config = None
        if request.config:
            config = ValidatorConfig(**request.config)
        
        # Create validator
        validator_id = validator_registry.create_validator(
            validator_type=request.validator_type,
            validator_code=request.validator_code,
            validator_id=request.validator_id,
            config=config
        )
        
        # Get validator metadata
        validator = validator_registry.get_validator(validator_id)
        if not validator:
            raise HTTPException(status_code=500, detail="Failed to retrieve created validator")
        
        metadata = validator_registry.validator_metadata.get(validator_id, {})
        
        return ValidatorResponse(
            validator_id=validator_id,
            validator_type=request.validator_type.value,
            created_at=datetime.utcnow(),
            config=metadata.get("config", {}),
            healthy=True
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating validator: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=List[ValidatorResponse])
async def list_validators(validator_type: Optional[ValidatorType] = None):
    """
    List all registered validators.
    
    Optionally filter by validator type.
    """
    try:
        validators = validator_registry.list_validators(validator_type)
        
        return [
            ValidatorResponse(
                validator_id=v["validator_id"],
                validator_type=v["validator_type"],
                created_at=v.get("created_at"),
                config=v.get("config", {}),
                healthy=v.get("healthy", True)
            )
            for v in validators
        ]
        
    except Exception as e:
        logger.error(f"Error listing validators: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{validator_id}", response_model=ValidatorResponse)
async def get_validator(validator_id: str):
    """Get validator details by ID."""
    try:
        validator = validator_registry.get_validator(validator_id)
        if not validator:
            raise HTTPException(status_code=404, detail="Validator not found")
        
        metadata = validator_registry.validator_metadata.get(validator_id, {})
        
        return ValidatorResponse(
            validator_id=validator_id,
            validator_type=metadata.get("validator_type", "unknown"),
            created_at=metadata.get("created_at"),
            config=metadata.get("config", {}),
            healthy=True  # TODO: Implement health check
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting validator {validator_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{validator_id}")
async def delete_validator(validator_id: str):
    """Delete a validator."""
    try:
        success = validator_registry.remove_validator(validator_id)
        if not success:
            raise HTTPException(status_code=404, detail="Validator not found")
        
        return {"message": f"Validator {validator_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting validator {validator_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{validator_id}/execute", response_model=ExecutionResponse)
async def execute_validator(
    validator_id: str, 
    request: ValidatorExecuteRequest,
    background_tasks: BackgroundTasks
):
    """
    Execute a validator with input data.
    
    Supports both synchronous and asynchronous execution modes.
    Results are cached by default for performance.
    """
    try:
        # Get validator
        validator = validator_registry.get_validator(validator_id)
        if not validator:
            raise HTTPException(status_code=404, detail="Validator not found")
        
        # Create execution context
        context = ExecutionContext(
            user_id=request.context.get("user_id") if request.context else None,
            workspace_id=request.context.get("workspace_id") if request.context else None,
            async_execution=request.async_execution,
            cache_results=request.cache_results,
            metadata=request.context or {}
        )
        
        # Execute validator
        result = await validator_executor.execute_validator(
            validator=validator,
            input_data=request.input_data,
            context=context
        )
        
        return ExecutionResponse(
            execution_id=result.execution_id,
            validator_id=result.validator_id,
            status=result.status.value,
            started_at=result.started_at,
            completed_at=result.completed_at,
            execution_time_ms=result.execution_time_ms,
            is_valid=result.is_valid,
            confidence_score=result.confidence_score,
            output_data=result.output_data,
            error=result.error.to_dict() if result.error else None,
            metadata=result.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing validator {validator_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{validator_id}/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution_status(validator_id: str, execution_id: str):
    """Get status of a validator execution."""
    try:
        result = await validator_executor.get_execution_status(execution_id)
        if not result:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        # Verify validator ID matches
        if result.validator_id != validator_id:
            raise HTTPException(status_code=400, detail="Execution does not belong to this validator")
        
        return ExecutionResponse(
            execution_id=result.execution_id,
            validator_id=result.validator_id,
            status=result.status.value,
            started_at=result.started_at,
            completed_at=result.completed_at,
            execution_time_ms=result.execution_time_ms,
            is_valid=result.is_valid,
            confidence_score=result.confidence_score,
            output_data=result.output_data,
            error=result.error.to_dict() if result.error else None,
            metadata=result.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting execution status {execution_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{validator_id}/executions/{execution_id}")
async def cancel_execution(validator_id: str, execution_id: str):
    """Cancel a running validator execution."""
    try:
        success = await validator_executor.cancel_execution(execution_id)
        if not success:
            raise HTTPException(status_code=404, detail="Execution not found or cannot be cancelled")
        
        return {"message": f"Execution {execution_id} cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling execution {execution_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{validator_id}/health")
async def check_validator_health(validator_id: str):
    """Check validator health status."""
    try:
        validator = validator_registry.get_validator(validator_id)
        if not validator:
            raise HTTPException(status_code=404, detail="Validator not found")
        
        is_healthy = await validator.health_check()
        
        return {
            "validator_id": validator_id,
            "healthy": is_healthy,
            "checked_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking validator health {validator_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/registry")
async def get_registry_stats():
    """Get validator registry statistics."""
    try:
        stats = validator_registry.get_stats()
        executor_stats = validator_executor.get_stats()
        
        return {
            "registry": stats,
            "executor": executor_stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/health/check-all")
async def health_check_all_validators():
    """Run health checks on all validators."""
    try:
        health_status = await validator_registry.health_check_all()
        
        return {
            "health_status": health_status,
            "total_validators": len(health_status),
            "healthy_validators": sum(1 for status in health_status.values() if status),
            "checked_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error running health checks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
