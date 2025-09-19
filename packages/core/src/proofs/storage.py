"""
Proof Storage - Story 9: Basic Proof Generation

Handles immutable storage and retrieval of generated proofs.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
import asyncio

from ..storage import StorageManager, Artifact, ArtifactMetadata, StorageError
from .interface import ProofData, ProofFormat, ProofConfig, ProofError

logger = logging.getLogger(__name__)


class ProofStorage:
    """Immutable proof storage with artifact integration."""
    
    def __init__(self, storage_manager: StorageManager, config: ProofConfig):
        self.storage_manager = storage_manager
        self.config = config
        self.stats = {
            "total_stored": 0,
            "total_retrieved": 0,
            "storage_errors": 0,
            "retrieval_errors": 0
        }
    
    async def store_proof(self, proof_data: ProofData, serialized_proof: bytes, **kwargs) -> str:
        """Store proof as immutable artifact."""
        start_time = datetime.utcnow()
        
        try:
            metadata = ArtifactMetadata(
                artifact_id=proof_data.proof_id,
                workspace_id=proof_data.validation_result.workspace_id,
                owner_id=proof_data.validation_result.user_id,
                artifact_type="proof",
                content_type=self._get_content_type(proof_data.metadata.proof_format),
                size_bytes=len(serialized_proof),
                expires_at=proof_data.metadata.expires_at,
                tags={
                    "proof_format": proof_data.metadata.proof_format.value,
                    "validator_id": proof_data.validation_result.validator_id,
                    "execution_id": proof_data.validation_result.execution_id,
                    "is_valid": str(proof_data.validation_result.is_valid)
                }
            )
            
            artifact = await self.storage_manager.store_artifact(
                content=serialized_proof,
                metadata=metadata,
                immutable=self.config.enable_immutable_storage,
                **kwargs
            )
            
            proof_data.metadata.storage_path = artifact.metadata.artifact_id
            self.stats["total_stored"] += 1
            
            storage_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(f"Stored proof {proof_data.proof_id} in {storage_time:.2f}ms")
            
            return artifact.metadata.artifact_id
            
        except Exception as e:
            self.stats["storage_errors"] += 1
            logger.error(f"Failed to store proof {proof_data.proof_id}: {e}")
            raise ProofError(f"Proof storage failed: {e}", error_code="STORAGE_ERROR")
    
    async def retrieve_proof(self, proof_id: str, workspace_id: Optional[str] = None) -> Optional[bytes]:
        """Retrieve proof by ID."""
        try:
            artifact = await self.storage_manager.retrieve_artifact(
                artifact_id=proof_id,
                workspace_id=workspace_id,
                include_content=True
            )
            
            if not artifact or artifact.metadata.artifact_type != "proof":
                return None
            
            self.stats["total_retrieved"] += 1
            return artifact.content
            
        except Exception as e:
            self.stats["retrieval_errors"] += 1
            logger.error(f"Failed to retrieve proof {proof_id}: {e}")
            raise ProofError(f"Proof retrieval failed: {e}", error_code="RETRIEVAL_ERROR")
    
    def _get_content_type(self, proof_format: ProofFormat) -> str:
        """Get content type for proof format."""
        content_types = {
            ProofFormat.JSON: "application/json",
            ProofFormat.JWT: "application/jwt",
            ProofFormat.XML: "application/xml",
            ProofFormat.BINARY: "application/octet-stream"
        }
        return content_types.get(proof_format, "application/octet-stream")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        return self.stats.copy()
    
    async def health_check(self) -> bool:
        """Check proof storage health."""
        try:
            return await self.storage_manager.health_check()
        except Exception as e:
            logger.error(f"Proof storage health check failed: {e}")
            return False


# Global proof storage instance
proof_storage = None
