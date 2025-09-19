"""
Storage Interface Definition - Story 8: Artifact Storage System

Defines the core interfaces for artifact storage following senior engineer patterns.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union, AsyncGenerator, BinaryIO
import hashlib
import uuid


class StorageBackend(str, Enum):
    """Supported storage backend types."""
    S3 = "s3"
    LOCAL = "local"
    AZURE = "azure"
    GCS = "gcs"


class AccessPermission(str, Enum):
    """Access permission levels."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


@dataclass
class RetentionPolicy:
    """Artifact retention policy configuration."""
    
    # Retention settings
    default_retention_days: int = 90
    max_retention_days: int = 365
    min_retention_days: int = 1
    
    # Lifecycle management
    auto_delete_enabled: bool = True
    archive_after_days: Optional[int] = 30
    
    # Compliance settings
    legal_hold_enabled: bool = False
    compliance_mode: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "default_retention_days": self.default_retention_days,
            "max_retention_days": self.max_retention_days,
            "min_retention_days": self.min_retention_days,
            "auto_delete_enabled": self.auto_delete_enabled,
            "archive_after_days": self.archive_after_days,
            "legal_hold_enabled": self.legal_hold_enabled,
            "compliance_mode": self.compliance_mode
        }


@dataclass
class StorageConfig:
    """Configuration for storage backend."""
    
    # Backend settings
    backend: StorageBackend = StorageBackend.S3
    endpoint_url: Optional[str] = None
    region: str = "us-east-1"
    bucket_name: str = "runlayer-artifacts"
    
    # Authentication
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None
    
    # Performance settings
    multipart_threshold: int = 64 * 1024 * 1024  # 64MB
    max_concurrency: int = 10
    max_bandwidth: Optional[int] = None
    
    # Security settings
    encryption_enabled: bool = True
    encryption_key: Optional[str] = None
    ssl_verify: bool = True
    
    # CDN settings
    cdn_enabled: bool = False
    cdn_domain: Optional[str] = None
    
    # Retention policy
    retention_policy: RetentionPolicy = field(default_factory=RetentionPolicy)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "backend": self.backend.value,
            "endpoint_url": self.endpoint_url,
            "region": self.region,
            "bucket_name": self.bucket_name,
            "access_key_id": self.access_key_id,
            "secret_access_key": "***" if self.secret_access_key else None,
            "session_token": "***" if self.session_token else None,
            "multipart_threshold": self.multipart_threshold,
            "max_concurrency": self.max_concurrency,
            "max_bandwidth": self.max_bandwidth,
            "encryption_enabled": self.encryption_enabled,
            "encryption_key": "***" if self.encryption_key else None,
            "ssl_verify": self.ssl_verify,
            "cdn_enabled": self.cdn_enabled,
            "cdn_domain": self.cdn_domain,
            "retention_policy": self.retention_policy.to_dict()
        }


@dataclass
class ArtifactMetadata:
    """Metadata for stored artifacts."""
    
    # Identification
    artifact_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content_hash: str = ""  # SHA-256 hash
    original_filename: Optional[str] = None
    
    # Content information
    content_type: str = "application/octet-stream"
    content_length: int = 0
    content_encoding: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    modified_at: datetime = field(default_factory=datetime.utcnow)
    accessed_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    # Ownership and permissions
    owner_id: Optional[str] = None
    workspace_id: Optional[str] = None
    permissions: Dict[str, List[AccessPermission]] = field(default_factory=dict)
    
    # Storage information
    storage_backend: StorageBackend = StorageBackend.S3
    storage_path: str = ""
    storage_class: str = "STANDARD"
    
    # Validation context
    validator_id: Optional[str] = None
    execution_id: Optional[str] = None
    proof_id: Optional[str] = None
    
    # Custom metadata
    tags: Dict[str, str] = field(default_factory=dict)
    custom_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "artifact_id": self.artifact_id,
            "content_hash": self.content_hash,
            "original_filename": self.original_filename,
            "content_type": self.content_type,
            "content_length": self.content_length,
            "content_encoding": self.content_encoding,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "accessed_at": self.accessed_at.isoformat() if self.accessed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "owner_id": self.owner_id,
            "workspace_id": self.workspace_id,
            "permissions": {k: [p.value for p in v] for k, v in self.permissions.items()},
            "storage_backend": self.storage_backend.value,
            "storage_path": self.storage_path,
            "storage_class": self.storage_class,
            "validator_id": self.validator_id,
            "execution_id": self.execution_id,
            "proof_id": self.proof_id,
            "tags": self.tags,
            "custom_metadata": self.custom_metadata
        }


@dataclass
class Artifact:
    """Represents a stored artifact with its metadata and content."""
    
    metadata: ArtifactMetadata
    content: Optional[bytes] = None
    content_stream: Optional[BinaryIO] = None
    
    @property
    def size(self) -> int:
        """Get artifact size."""
        return self.metadata.content_length
    
    @property
    def hash(self) -> str:
        """Get content hash."""
        return self.metadata.content_hash
    
    @property
    def is_expired(self) -> bool:
        """Check if artifact has expired."""
        if self.metadata.expires_at:
            return datetime.utcnow() > self.metadata.expires_at
        return False
    
    def calculate_hash(self) -> str:
        """Calculate SHA-256 hash of content."""
        if self.content:
            return hashlib.sha256(self.content).hexdigest()
        elif self.content_stream:
            hasher = hashlib.sha256()
            self.content_stream.seek(0)
            for chunk in iter(lambda: self.content_stream.read(8192), b""):
                hasher.update(chunk)
            self.content_stream.seek(0)
            return hasher.hexdigest()
        return ""
    
    def update_hash(self) -> None:
        """Update metadata hash from content."""
        self.metadata.content_hash = self.calculate_hash()


class StorageError(Exception):
    """Base exception for storage operations."""
    
    def __init__(self, message: str, error_code: str = "STORAGE_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class StorageInterface(ABC):
    """Abstract interface for artifact storage backends."""
    
    def __init__(self, config: StorageConfig):
        self.config = config
    
    @abstractmethod
    async def store_artifact(
        self,
        content: Union[bytes, BinaryIO],
        metadata: Optional[ArtifactMetadata] = None,
        **kwargs
    ) -> Artifact:
        """
        Store an artifact with optional metadata.
        
        Args:
            content: Artifact content as bytes or stream
            metadata: Optional artifact metadata
            **kwargs: Additional storage options
            
        Returns:
            Stored artifact with metadata
            
        Raises:
            StorageError: If storage operation fails
        """
        pass
    
    @abstractmethod
    async def retrieve_artifact(
        self,
        artifact_id: str,
        include_content: bool = True
    ) -> Optional[Artifact]:
        """
        Retrieve an artifact by ID.
        
        Args:
            artifact_id: Unique artifact identifier
            include_content: Whether to include content in response
            
        Returns:
            Artifact if found, None otherwise
            
        Raises:
            StorageError: If retrieval operation fails
        """
        pass
    
    @abstractmethod
    async def retrieve_by_hash(
        self,
        content_hash: str,
        include_content: bool = True
    ) -> Optional[Artifact]:
        """
        Retrieve an artifact by content hash.
        
        Args:
            content_hash: SHA-256 content hash
            include_content: Whether to include content in response
            
        Returns:
            Artifact if found, None otherwise
        """
        pass
    
    @abstractmethod
    async def delete_artifact(self, artifact_id: str) -> bool:
        """
        Delete an artifact.
        
        Args:
            artifact_id: Unique artifact identifier
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            StorageError: If deletion operation fails
        """
        pass
    
    @abstractmethod
    async def list_artifacts(
        self,
        workspace_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ArtifactMetadata]:
        """
        List artifacts with optional filtering.
        
        Args:
            workspace_id: Filter by workspace
            owner_id: Filter by owner
            tags: Filter by tags
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of artifact metadata
        """
        pass
    
    @abstractmethod
    async def get_artifact_url(
        self,
        artifact_id: str,
        expires_in: int = 3600,
        permission: AccessPermission = AccessPermission.READ
    ) -> str:
        """
        Generate a presigned URL for artifact access.
        
        Args:
            artifact_id: Unique artifact identifier
            expires_in: URL expiration time in seconds
            permission: Required permission level
            
        Returns:
            Presigned URL for artifact access
        """
        pass
    
    @abstractmethod
    async def check_permissions(
        self,
        artifact_id: str,
        user_id: str,
        permission: AccessPermission
    ) -> bool:
        """
        Check if user has permission for artifact.
        
        Args:
            artifact_id: Unique artifact identifier
            user_id: User identifier
            permission: Required permission
            
        Returns:
            True if permission granted, False otherwise
        """
        pass
    
    @abstractmethod
    async def update_metadata(
        self,
        artifact_id: str,
        metadata_updates: Dict[str, Any]
    ) -> bool:
        """
        Update artifact metadata.
        
        Args:
            artifact_id: Unique artifact identifier
            metadata_updates: Metadata fields to update
            
        Returns:
            True if updated successfully, False if not found
        """
        pass
    
    @abstractmethod
    async def cleanup_expired(self) -> int:
        """
        Clean up expired artifacts based on retention policy.
        
        Returns:
            Number of artifacts cleaned up
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check storage backend health.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    def get_config(self) -> Dict[str, Any]:
        """Get storage configuration (sanitized)."""
        return self.config.to_dict()
