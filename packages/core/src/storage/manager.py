"""
Storage Manager - Story 8: Artifact Storage System
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, BinaryIO

from .interface import (
    StorageInterface, StorageConfig, Artifact, ArtifactMetadata,
    StorageError, AccessPermission, StorageBackend
)
from .s3_storage import S3StorageBackend
from .content_store import ContentAddressedStorage

logger = logging.getLogger(__name__)


class StorageManager:
    """Central storage manager with deduplication and access control."""
    
    def __init__(self, config: StorageConfig):
        self.config = config
        self.backend = self._create_backend(config)
        self.content_store = ContentAddressedStorage(self.backend)
        self.stats = {"operations": 0, "bytes_stored": 0}
    
    def _create_backend(self, config: StorageConfig) -> StorageInterface:
        """Create storage backend."""
        if config.backend == StorageBackend.S3:
            return S3StorageBackend(config)
        raise StorageError(
            f"Unsupported storage backend: {config.backend}",
            error_code="UNSUPPORTED_BACKEND"
        )
    
    async def store_artifact(self, content: Union[bytes, BinaryIO], 
                           metadata: ArtifactMetadata = None, **kwargs) -> Artifact:
        """Store artifact with deduplication."""
        if not metadata:
            metadata = ArtifactMetadata()
        
        # Set retention
        if not metadata.expires_at:
            metadata.expires_at = datetime.utcnow() + timedelta(
                days=self.config.retention_policy.default_retention_days
            )
        
        artifact = await self.content_store.store_with_deduplication(content, metadata)
        self.stats["operations"] += 1
        return artifact
    
    async def retrieve_artifact(self, artifact_id: str, user_id: str = None) -> Optional[Artifact]:
        """Retrieve artifact with permissions."""
        if user_id:
            has_permission = await self.backend.check_permissions(
                artifact_id, user_id, AccessPermission.READ
            )
            if not has_permission:
                return None
        
        return await self.backend.retrieve_artifact(artifact_id)
    
    async def delete_artifact(self, artifact_id: str, user_id: str = None) -> bool:
        """Delete artifact with cleanup."""
        if user_id:
            has_permission = await self.backend.check_permissions(
                artifact_id, user_id, AccessPermission.DELETE
            )
            if not has_permission:
                return False
        
        return await self.content_store.delete_with_cleanup(artifact_id)
    
    async def cleanup_expired_artifacts(self) -> int:
        """Cleanup expired artifacts."""
        backend_cleaned = await self.backend.cleanup_expired()
        gc_cleaned = await self.content_store.garbage_collect()
        return backend_cleaned + gc_cleaned
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        dedup_stats = await self.content_store.get_deduplication_stats()
        return {**self.stats, "deduplication": dedup_stats}
    
    async def health_check(self) -> bool:
        """Check storage health."""
        return await self.backend.health_check()
    
    def _update_stats(self, start_time: datetime, success: bool, bytes_count: int):
        """Update performance statistics."""
        self.stats["operations"] += 1
        if success:
            self.stats["bytes_stored"] += bytes_count


# Global storage manager instance
storage_manager = StorageManager(StorageConfig())
