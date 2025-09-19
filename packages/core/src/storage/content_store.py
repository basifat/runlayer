"""
Content-Addressed Storage - Story 8: Artifact Storage System

Implements content-addressed storage with SHA-256 hashing and deduplication.
"""

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, BinaryIO
import asyncio

from .interface import (
    StorageInterface, StorageConfig, Artifact, ArtifactMetadata,
    StorageError, AccessPermission, StorageBackend
)

logger = logging.getLogger(__name__)


class ContentAddressedStorage:
    """
    Content-addressed storage layer for artifact deduplication.
    
    Features:
    - SHA-256 content addressing
    - Automatic deduplication
    - Reference counting
    - Garbage collection
    """
    
    def __init__(self, backend: StorageInterface):
        self.backend = backend
        self.content_index: Dict[str, List[str]] = {}  # hash -> [artifact_ids]
        self.reference_counts: Dict[str, int] = {}  # hash -> count
    
    async def store_with_deduplication(
        self,
        content: Union[bytes, BinaryIO],
        metadata: ArtifactMetadata
    ) -> Artifact:
        """Store content with automatic deduplication."""
        
        # Calculate content hash
        content_hash = self._calculate_hash(content)
        metadata.content_hash = content_hash
        
        # Check if content already exists
        if content_hash in self.content_index:
            logger.info(f"Content hash {content_hash} already exists, deduplicating")
            
            # Increment reference count
            self.reference_counts[content_hash] = self.reference_counts.get(content_hash, 0) + 1
            
            # Add artifact ID to index
            if metadata.artifact_id not in self.content_index[content_hash]:
                self.content_index[content_hash].append(metadata.artifact_id)
            
            # Return existing content with new metadata
            existing_artifact = await self.backend.retrieve_by_hash(content_hash, include_content=True)
            if existing_artifact:
                # Update metadata but keep existing content
                new_artifact = Artifact(metadata=metadata, content=existing_artifact.content)
                return new_artifact
        
        # Store new content
        artifact = await self.backend.store_artifact(content, metadata)
        
        # Update indexes
        if content_hash not in self.content_index:
            self.content_index[content_hash] = []
        
        if metadata.artifact_id not in self.content_index[content_hash]:
            self.content_index[content_hash].append(metadata.artifact_id)
        
        self.reference_counts[content_hash] = self.reference_counts.get(content_hash, 0) + 1
        
        return artifact
    
    async def delete_with_cleanup(self, artifact_id: str) -> bool:
        """Delete artifact with reference counting cleanup."""
        
        # Find content hash for artifact
        content_hash = None
        for hash_key, artifact_ids in self.content_index.items():
            if artifact_id in artifact_ids:
                content_hash = hash_key
                break
        
        if not content_hash:
            logger.warning(f"Artifact {artifact_id} not found in content index")
            return await self.backend.delete_artifact(artifact_id)
        
        # Remove from index
        self.content_index[content_hash].remove(artifact_id)
        
        # Decrement reference count
        self.reference_counts[content_hash] = max(0, self.reference_counts.get(content_hash, 1) - 1)
        
        # If no more references, delete actual content
        if self.reference_counts[content_hash] == 0:
            logger.info(f"No more references to {content_hash}, deleting content")
            
            # Delete all artifacts with this hash
            for aid in self.content_index[content_hash]:
                await self.backend.delete_artifact(aid)
            
            # Clean up indexes
            del self.content_index[content_hash]
            del self.reference_counts[content_hash]
            
            return True
        
        logger.info(f"Content {content_hash} still has {self.reference_counts[content_hash]} references")
        return True
    
    async def get_deduplication_stats(self) -> Dict[str, Any]:
        """Get deduplication statistics."""
        total_artifacts = sum(len(artifact_ids) for artifact_ids in self.content_index.values())
        unique_content = len(self.content_index)
        
        deduplication_ratio = 0.0
        if unique_content > 0:
            deduplication_ratio = (total_artifacts - unique_content) / total_artifacts
        
        return {
            "total_artifacts": total_artifacts,
            "unique_content_items": unique_content,
            "deduplication_ratio": deduplication_ratio,
            "space_saved_percent": deduplication_ratio * 100,
            "reference_counts": dict(self.reference_counts)
        }
    
    async def garbage_collect(self) -> int:
        """Run garbage collection to clean up unreferenced content."""
        cleaned_count = 0
        
        for content_hash in list(self.content_index.keys()):
            if self.reference_counts.get(content_hash, 0) == 0:
                logger.info(f"Garbage collecting unreferenced content: {content_hash}")
                
                # Delete all artifacts with this hash
                for artifact_id in self.content_index[content_hash]:
                    await self.backend.delete_artifact(artifact_id)
                    cleaned_count += 1
                
                # Clean up indexes
                del self.content_index[content_hash]
                if content_hash in self.reference_counts:
                    del self.reference_counts[content_hash]
        
        return cleaned_count
    
    def _calculate_hash(self, content: Union[bytes, BinaryIO]) -> str:
        """Calculate SHA-256 hash of content."""
        hasher = hashlib.sha256()
        
        if isinstance(content, bytes):
            hasher.update(content)
        else:
            content.seek(0)
            for chunk in iter(lambda: content.read(8192), b""):
                hasher.update(chunk)
            content.seek(0)
        
        return hasher.hexdigest()
    
    async def verify_integrity(self) -> Dict[str, Any]:
        """Verify content integrity across all stored artifacts."""
        verification_results = {
            "verified_count": 0,
            "corrupted_count": 0,
            "missing_count": 0,
            "corrupted_artifacts": [],
            "missing_artifacts": []
        }
        
        for content_hash, artifact_ids in self.content_index.items():
            for artifact_id in artifact_ids:
                try:
                    artifact = await self.backend.retrieve_artifact(artifact_id, include_content=True)
                    
                    if not artifact:
                        verification_results["missing_count"] += 1
                        verification_results["missing_artifacts"].append(artifact_id)
                        continue
                    
                    # Verify hash matches content
                    calculated_hash = self._calculate_hash(artifact.content)
                    if calculated_hash != content_hash:
                        verification_results["corrupted_count"] += 1
                        verification_results["corrupted_artifacts"].append({
                            "artifact_id": artifact_id,
                            "expected_hash": content_hash,
                            "actual_hash": calculated_hash
                        })
                    else:
                        verification_results["verified_count"] += 1
                
                except Exception as e:
                    logger.error(f"Error verifying artifact {artifact_id}: {e}")
                    verification_results["corrupted_count"] += 1
                    verification_results["corrupted_artifacts"].append({
                        "artifact_id": artifact_id,
                        "error": str(e)
                    })
        
        return verification_results
