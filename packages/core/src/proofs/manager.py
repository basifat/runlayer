"""
Proof Manager - Story 9: Basic Proof Generation

Orchestrates the complete proof generation workflow.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import asyncio

from ..storage import storage_manager
from .interface import ProofData, ValidationResult, ProofFormat, ProofConfig, ProofError
from .generator import ProofGenerator
from .storage import ProofStorage

logger = logging.getLogger(__name__)


class ProofManager:
    """
    Complete proof management system.
    
    Features:
    - End-to-end proof generation workflow
    - Integration with validator execution results
    - Immutable proof storage
    - Performance optimization (<3 seconds)
    - Comprehensive error handling
    """
    
    def __init__(self, config: ProofConfig = None):
        self.config = config or ProofConfig()
        
        # Initialize components
        self.generator = ProofGenerator(self.config)
        self.storage = ProofStorage(storage_manager, self.config)
        
        # Performance tracking
        self.stats = {
            "total_proofs_generated": 0,
            "successful_proofs": 0,
            "failed_proofs": 0,
            "average_end_to_end_time_ms": 0.0
        }
    
    async def create_proof(
        self,
        validation_result: ValidationResult,
        proof_format: Optional[ProofFormat] = None,
        store_proof: bool = True,
        **kwargs
    ) -> ProofData:
        """
        Create complete proof from validation results.
        
        Args:
            validation_result: Validation result to create proof from
            proof_format: Optional format override
            store_proof: Whether to store proof in artifact storage
            **kwargs: Additional options
            
        Returns:
            Generated and optionally stored proof data
        """
        start_time = datetime.utcnow()
        
        try:
            # Generate proof
            proof_data = await self.generator.generate_proof(
                validation_result=validation_result,
                proof_format=proof_format,
                **kwargs
            )
            
            # Store proof if requested
            if store_proof:
                serialized_proof = await self.generator.serialize_proof(proof_data)
                storage_path = await self.storage.store_proof(
                    proof_data=proof_data,
                    serialized_proof=serialized_proof
                )
                proof_data.metadata.storage_path = storage_path
            
            # Update statistics
            end_to_end_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._update_stats(end_to_end_time, True)
            
            # Validate performance requirement
            if end_to_end_time > self.config.max_generation_time_seconds * 1000:
                logger.warning(
                    f"Proof creation took {end_to_end_time:.2f}ms, "
                    f"exceeding {self.config.max_generation_time_seconds * 1000}ms limit"
                )
            
            logger.info(
                f"Created proof {proof_data.proof_id} in {end_to_end_time:.2f}ms "
                f"(stored: {store_proof})"
            )
            
            return proof_data
            
        except Exception as e:
            end_to_end_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._update_stats(end_to_end_time, False)
            
            logger.error(f"Failed to create proof: {e}")
            
            if isinstance(e, ProofError):
                raise
            else:
                raise ProofError(
                    f"Proof creation failed: {e}",
                    error_code="CREATION_ERROR",
                    details={"error": str(e), "end_to_end_time_ms": end_to_end_time}
                )
    
    async def get_proof(
        self,
        proof_id: str,
        workspace_id: Optional[str] = None,
        deserialize: bool = True
    ) -> Optional[Union[ProofData, bytes]]:
        """
        Retrieve proof by ID.
        
        Args:
            proof_id: Proof ID to retrieve
            workspace_id: Optional workspace filter
            deserialize: Whether to deserialize proof data
            
        Returns:
            ProofData if deserialize=True, bytes if False, None if not found
        """
        try:
            # Retrieve serialized proof
            serialized_proof = await self.storage.retrieve_proof(
                proof_id=proof_id,
                workspace_id=workspace_id
            )
            
            if not serialized_proof:
                return None
            
            if not deserialize:
                return serialized_proof
            
            # Deserialize proof - we need to determine format
            # For now, assume JSON format (could be enhanced to detect format)
            proof_data = await self.generator.deserialize_proof(
                proof_bytes=serialized_proof,
                format=ProofFormat.JSON
            )
            
            return proof_data
            
        except Exception as e:
            logger.error(f"Failed to get proof {proof_id}: {e}")
            
            if isinstance(e, ProofError):
                raise
            else:
                raise ProofError(
                    f"Proof retrieval failed: {e}",
                    error_code="RETRIEVAL_ERROR",
                    details={"error": str(e)}
                )
    
    async def validate_proof(
        self,
        proof_data: Union[ProofData, str],
        strict: bool = True
    ) -> bool:
        """
        Validate proof data or retrieve and validate by ID.
        
        Args:
            proof_data: ProofData object or proof ID string
            strict: Whether to perform strict validation
            
        Returns:
            True if proof is valid, False otherwise
        """
        try:
            # If string, retrieve proof first
            if isinstance(proof_data, str):
                retrieved_proof = await self.get_proof(proof_data, deserialize=True)
                if not retrieved_proof:
                    logger.error(f"Proof {proof_data} not found for validation")
                    return False
                proof_data = retrieved_proof
            
            # Validate using generator
            return await self.generator.validate_proof(proof_data, strict=strict)
            
        except Exception as e:
            logger.error(f"Proof validation error: {e}")
            return False
    
    async def list_proofs(
        self,
        workspace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        validator_id: Optional[str] = None,
        is_valid: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List proofs with filtering options."""
        try:
            # Use storage layer for listing (if implemented)
            # For now, return empty list as storage.list_proofs is not in the simplified version
            logger.warning("Proof listing not yet implemented in storage layer")
            return []
            
        except Exception as e:
            logger.error(f"Failed to list proofs: {e}")
            raise ProofError(
                f"Proof listing failed: {e}",
                error_code="LISTING_ERROR"
            )
    
    def _update_stats(self, end_to_end_time_ms: float, success: bool) -> None:
        """Update proof creation statistics."""
        self.stats["total_proofs_generated"] += 1
        
        if success:
            self.stats["successful_proofs"] += 1
            
            # Update average end-to-end time
            total_successful = self.stats["successful_proofs"]
            current_avg = self.stats["average_end_to_end_time_ms"]
            self.stats["average_end_to_end_time_ms"] = (
                (current_avg * (total_successful - 1) + end_to_end_time_ms) / total_successful
            )
        else:
            self.stats["failed_proofs"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive proof management statistics."""
        return {
            **self.stats,
            "generator_stats": self.generator.get_stats(),
            "storage_stats": self.storage.get_stats(),
            "config": self.config.to_dict()
        }
    
    def get_supported_formats(self) -> List[ProofFormat]:
        """Get supported proof formats."""
        return self.generator.get_supported_formats()
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check for proof system."""
        try:
            # Check generator health
            generator_healthy = await self.generator.health_check()
            
            # Check storage health
            storage_healthy = await self.storage.health_check()
            
            # Overall health
            overall_healthy = generator_healthy and storage_healthy
            
            return {
                "status": "healthy" if overall_healthy else "unhealthy",
                "components": {
                    "generator": "healthy" if generator_healthy else "unhealthy",
                    "storage": "healthy" if storage_healthy else "unhealthy"
                },
                "supported_formats": [f.value for f in self.get_supported_formats()],
                "stats": self.get_stats()
            }
            
        except Exception as e:
            logger.error(f"Proof manager health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "components": {
                    "generator": "unknown",
                    "storage": "unknown"
                }
            }


# Global proof manager instance
proof_manager = ProofManager()
