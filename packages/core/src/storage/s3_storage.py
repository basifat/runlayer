"""
S3-Compatible Storage Backend - Story 8: Artifact Storage System
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, BinaryIO
import uuid
import io

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from .interface import (
    StorageInterface, StorageConfig, Artifact, ArtifactMetadata,
    StorageError, AccessPermission, StorageBackend
)

logger = logging.getLogger(__name__)


class S3StorageBackend(StorageInterface):
    """S3-compatible storage with content addressing and deduplication."""
    
    def __init__(self, config: StorageConfig):
        super().__init__(config)
        if not BOTO3_AVAILABLE:
            raise StorageError("boto3 required", error_code="DEPENDENCY_MISSING")
        
        self.client = boto3.client('s3',
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name=config.region,
            endpoint_url=config.endpoint_url
        )
        self.bucket_name = config.bucket_name
    
    def _calculate_hash(self, content: Union[bytes, BinaryIO]) -> str:
        """Calculate SHA-256 hash."""
        hasher = hashlib.sha256()
        if isinstance(content, bytes):
            hasher.update(content)
        else:
            content.seek(0)
            for chunk in iter(lambda: content.read(8192), b""):
                hasher.update(chunk)
            content.seek(0)
        return hasher.hexdigest()
    
    def _generate_path(self, content_hash: str, workspace_id: str = None) -> str:
        """Generate content-addressed path."""
        prefix = content_hash[:2]
        middle = content_hash[2:4]
        workspace_prefix = f"workspaces/{workspace_id}/" if workspace_id else ""
        return f"{workspace_prefix}artifacts/{prefix}/{middle}/{content_hash}"
    
    async def store_artifact(self, content: Union[bytes, BinaryIO], 
                           metadata: Optional[ArtifactMetadata] = None, **kwargs) -> Artifact:
        """Store artifact with deduplication."""
        if not metadata:
            metadata = ArtifactMetadata()
        
        try:
            # Calculate hash and check for existing
            content_hash = self._calculate_hash(content)
            existing = await self.retrieve_by_hash(content_hash, include_content=False)
            if existing:
                return existing
            
            # Store new artifact
            storage_path = self._generate_path(content_hash, metadata.workspace_id)
            metadata.content_hash = content_hash
            metadata.storage_path = storage_path
            metadata.storage_backend = StorageBackend.S3
            
            upload_params = {
                'Bucket': self.bucket_name,
                'Key': storage_path,
                'Body': content if isinstance(content, bytes) else content.read(),
                'Metadata': {
                    'artifact-id': metadata.artifact_id,
                    'content-hash': content_hash,
                    'workspace-id': metadata.workspace_id or ''
                }
            }
            
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.client.put_object(**upload_params)
            )
            
            return Artifact(metadata=metadata, content=upload_params['Body'])
            
        except ClientError as e:
            raise StorageError(f"S3 error: {e}", error_code="S3_ERROR")
    
    async def retrieve_artifact(self, artifact_id: str, include_content: bool = True) -> Optional[Artifact]:
        """Retrieve artifact by ID."""
        # Implementation would query metadata store and retrieve from S3
        pass
    
    async def retrieve_by_hash(self, content_hash: str, include_content: bool = True) -> Optional[Artifact]:
        """Retrieve artifact by hash."""
        # Implementation would check if hash exists
        pass
    
    async def delete_artifact(self, artifact_id: str) -> bool:
        """Delete artifact."""
        pass
    
    async def list_artifacts(self, workspace_id: str = None, **kwargs) -> List[ArtifactMetadata]:
        """List artifacts."""
        pass
    
    async def get_artifact_url(self, artifact_id: str, expires_in: int = 3600, 
                             permission: AccessPermission = AccessPermission.READ) -> str:
        """Generate presigned URL."""
        pass
    
    async def check_permissions(self, artifact_id: str, user_id: str, 
                              permission: AccessPermission) -> bool:
        """Check permissions."""
        pass
    
    async def update_metadata(self, artifact_id: str, metadata_updates: Dict[str, Any]) -> bool:
        """Update metadata."""
        pass
    
    async def cleanup_expired(self) -> int:
        """Cleanup expired artifacts."""
        pass
    
    async def health_check(self) -> bool:
        """Health check."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.client.head_bucket(Bucket=self.bucket_name)
            )
            return True
        except:
            return False
