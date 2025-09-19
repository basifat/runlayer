"""
Artifact Storage System - Story 8: Artifact Storage System

12-Factor App Compliance:
- III. Config: All storage configuration from environment
- IV. Backing Services: S3-compatible storage as attached resource
- VI. Processes: Stateless storage operations

DRY Principles Applied:
- Single StorageInterface for all storage backends
- Reusable content-addressing with SHA-256
- Centralized access control and permissions
- No code duplication across storage types
"""

from .interface import (
    StorageInterface,
    StorageBackend,
    Artifact,
    ArtifactMetadata,
    StorageError,
    StorageConfig,
    AccessPermission,
    RetentionPolicy
)
from .s3_storage import S3StorageBackend
from .content_store import ContentAddressedStorage
from .manager import StorageManager, storage_manager

__all__ = [
    "StorageInterface",
    "StorageBackend", 
    "Artifact",
    "ArtifactMetadata",
    "StorageError",
    "StorageConfig",
    "AccessPermission",
    "RetentionPolicy",
    "S3StorageBackend",
    "ContentAddressedStorage",
    "StorageManager",
    "storage_manager"
]
