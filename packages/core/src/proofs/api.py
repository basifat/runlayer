"""
Proof API Endpoints - Story 9: Basic Proof Generation
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel, Field

from .interface import ValidationResult, ProofFormat, ProofError
from .manager import proof_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/proofs", tags=["proofs"])


class CreateProofRequest(BaseModel):
    """Request model for proof creation."""
    validator_id: str
    execution_id: str
    workspace_id: str
    user_id: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    is_valid: bool
    confidence_score: Optional[float] = None
    execution_time_ms: float = 0.0
    proof_format: Optional[ProofFormat] = ProofFormat.JSON
    store_proof: bool = True


class ProofResponse(BaseModel):
    """Response model for proof operations."""
    proof_id: str
    proof_format: str
    workspace_id: str
    user_id: str
    validator_id: str
    execution_id: str
    is_valid: bool
    generated_at: datetime
    size_bytes: int
    generation_time_ms: float
    content_hash: str
    signature: Optional[str] = None


@router.post("/", response_model=ProofResponse, status_code=201)
async def create_proof(request: CreateProofRequest):
    """Create a new proof from validation results."""
    try:
        validation_result = ValidationResult(
            validator_id=request.validator_id,
            execution_id=request.execution_id,
            workspace_id=request.workspace_id,
            user_id=request.user_id,
            input_data=request.input_data,
            output_data=request.output_data,
            is_valid=request.is_valid,
            confidence_score=request.confidence_score,
            execution_time_ms=request.execution_time_ms
        )
        
        proof_data = await proof_manager.create_proof(
            validation_result=validation_result,
            proof_format=request.proof_format,
            store_proof=request.store_proof
        )
        
        return ProofResponse(
            proof_id=proof_data.proof_id,
            proof_format=proof_data.metadata.proof_format.value,
            workspace_id=proof_data.validation_result.workspace_id,
            user_id=proof_data.validation_result.user_id,
            validator_id=proof_data.validation_result.validator_id,
            execution_id=proof_data.validation_result.execution_id,
            is_valid=proof_data.validation_result.is_valid,
            generated_at=proof_data.metadata.generated_at,
            size_bytes=proof_data.metadata.size_bytes,
            generation_time_ms=proof_data.metadata.generation_time_ms,
            content_hash=proof_data.metadata.content_hash,
            signature=proof_data.metadata.signature
        )
        
    except ProofError as e:
        raise HTTPException(status_code=400, detail={"error": e.message, "error_code": e.error_code})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/{proof_id}", response_model=ProofResponse)
async def get_proof(proof_id: str = Path(...), workspace_id: Optional[str] = Query(None)):
    """Retrieve proof by ID."""
    try:
        proof_data = await proof_manager.get_proof(proof_id=proof_id, workspace_id=workspace_id)
        
        if not proof_data:
            raise HTTPException(status_code=404, detail="Proof not found")
        
        return ProofResponse(
            proof_id=proof_data.proof_id,
            proof_format=proof_data.metadata.proof_format.value,
            workspace_id=proof_data.validation_result.workspace_id,
            user_id=proof_data.validation_result.user_id,
            validator_id=proof_data.validation_result.validator_id,
            execution_id=proof_data.validation_result.execution_id,
            is_valid=proof_data.validation_result.is_valid,
            generated_at=proof_data.metadata.generated_at,
            size_bytes=proof_data.metadata.size_bytes,
            generation_time_ms=proof_data.metadata.generation_time_ms,
            content_hash=proof_data.metadata.content_hash,
            signature=proof_data.metadata.signature
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/", response_model=List[ProofResponse])
async def list_proofs(
    workspace_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    validator_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List proofs with filtering."""
    try:
        proofs = await proof_manager.list_proofs(
            workspace_id=workspace_id,
            user_id=user_id,
            validator_id=validator_id,
            limit=limit,
            offset=offset
        )
        return proofs
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """Check proof system health."""
    try:
        health_status = await proof_manager.health_check()
        return health_status
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})
