"""
Storage API Endpoints - Story 8: Artifact Storage System
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import io

from .manager import storage_manager
from .interface import ArtifactMetadata, AccessPermission, StorageError

router = APIRouter(prefix="/api/v1/storage", tags=["storage"])


# Request/Response Models
class ArtifactUploadRequest(BaseModel):
    """Request model for artifact upload."""
    workspace_id: Optional[str] = None
    owner_id: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)
    retention_days: Optional[int] = None


class ArtifactResponse(BaseModel):
    """Response model for artifact operations."""
    artifact_id: str
    content_hash: str
    content_type: str
    content_length: int
    created_at: datetime
    workspace_id: Optional[str]
    owner_id: Optional[str]
    storage_path: str
    tags: Dict[str, str]


class ArtifactListResponse(BaseModel):
    """Response model for artifact listing."""
    artifacts: List[ArtifactResponse]
    total_count: int
    page: int
    page_size: int


class StorageStatsResponse(BaseModel):
    """Response model for storage statistics."""
    total_operations: int
    bytes_stored: int
    deduplication: Dict[str, Any]


class PresignedUrlResponse(BaseModel):
    """Response model for presigned URLs."""
    url: str
    expires_at: datetime
    artifact_id: str


@router.post("/artifacts", response_model=ArtifactResponse)
async def upload_artifact(
    file: UploadFile = File(...),
    workspace_id: Optional[str] = Form(None),
    owner_id: Optional[str] = Form(None),
    tags: Optional[str] = Form("{}"),  # JSON string
    custom_metadata: Optional[str] = Form("{}"),  # JSON string
    retention_days: Optional[int] = Form(None)
):
    """Upload a new artifact."""
    try:
        import json
        
        # Parse JSON fields
        tags_dict = json.loads(tags) if tags else {}
        metadata_dict = json.loads(custom_metadata) if custom_metadata else {}
        
        # Create metadata
        metadata = ArtifactMetadata(
            original_filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            workspace_id=workspace_id,
            owner_id=owner_id,
            tags=tags_dict,
            custom_metadata=metadata_dict
        )
        
        # Set retention if specified
        if retention_days:
            from datetime import timedelta
            metadata.expires_at = datetime.utcnow() + timedelta(days=retention_days)
        
        # Read file content
        content = await file.read()
        metadata.content_length = len(content)
        
        # Store artifact
        artifact = await storage_manager.store_artifact(content, metadata)
        
        return ArtifactResponse(
            artifact_id=artifact.metadata.artifact_id,
            content_hash=artifact.metadata.content_hash,
            content_type=artifact.metadata.content_type,
            content_length=artifact.metadata.content_length,
            created_at=artifact.metadata.created_at,
            workspace_id=artifact.metadata.workspace_id,
            owner_id=artifact.metadata.owner_id,
            storage_path=artifact.metadata.storage_path,
            tags=artifact.metadata.tags
        )
        
    except StorageError as e:
        raise HTTPException(status_code=400, detail=f"Storage error: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact_metadata(
    artifact_id: str,
    user_id: Optional[str] = Query(None)
):
    """Get artifact metadata."""
    try:
        artifact = await storage_manager.retrieve_artifact(
            artifact_id, user_id=user_id
        )
        
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        
        return ArtifactResponse(
            artifact_id=artifact.metadata.artifact_id,
            content_hash=artifact.metadata.content_hash,
            content_type=artifact.metadata.content_type,
            content_length=artifact.metadata.content_length,
            created_at=artifact.metadata.created_at,
            workspace_id=artifact.metadata.workspace_id,
            owner_id=artifact.metadata.owner_id,
            storage_path=artifact.metadata.storage_path,
            tags=artifact.metadata.tags
        )
        
    except StorageError as e:
        raise HTTPException(status_code=400, detail=f"Storage error: {e.message}")


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: str,
    user_id: Optional[str] = Query(None)
):
    """Download artifact content."""
    try:
        artifact = await storage_manager.retrieve_artifact(
            artifact_id, user_id=user_id
        )
        
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        
        if not artifact.content:
            raise HTTPException(status_code=404, detail="Artifact content not available")
        
        # Create streaming response
        content_stream = io.BytesIO(artifact.content)
        
        return StreamingResponse(
            content_stream,
            media_type=artifact.metadata.content_type,
            headers={
                "Content-Disposition": f"attachment; filename={artifact.metadata.original_filename or artifact_id}",
                "Content-Length": str(artifact.metadata.content_length)
            }
        )
        
    except StorageError as e:
        raise HTTPException(status_code=400, detail=f"Storage error: {e.message}")


@router.delete("/artifacts/{artifact_id}")
async def delete_artifact(
    artifact_id: str,
    user_id: Optional[str] = Query(None)
):
    """Delete an artifact."""
    try:
        success = await storage_manager.delete_artifact(
            artifact_id, user_id=user_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Artifact not found or access denied")
        
        return {"message": "Artifact deleted successfully", "artifact_id": artifact_id}
        
    except StorageError as e:
        raise HTTPException(status_code=400, detail=f"Storage error: {e.message}")


@router.get("/artifacts", response_model=ArtifactListResponse)
async def list_artifacts(
    workspace_id: Optional[str] = Query(None),
    owner_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000)
):
    """List artifacts with filtering."""
    try:
        offset = (page - 1) * page_size
        
        artifacts = await storage_manager.backend.list_artifacts(
            workspace_id=workspace_id,
            owner_id=owner_id,
            limit=page_size,
            offset=offset
        )
        
        # Filter by user permissions if specified
        if user_id:
            filtered_artifacts = []
            for artifact in artifacts:
                has_permission = await storage_manager.backend.check_permissions(
                    artifact.artifact_id, user_id, AccessPermission.READ
                )
                if has_permission:
                    filtered_artifacts.append(artifact)
            artifacts = filtered_artifacts
        
        # Convert to response format
        artifact_responses = [
            ArtifactResponse(
                artifact_id=a.artifact_id,
                content_hash=a.content_hash,
                content_type=a.content_type,
                content_length=a.content_length,
                created_at=a.created_at,
                workspace_id=a.workspace_id,
                owner_id=a.owner_id,
                storage_path=a.storage_path,
                tags=a.tags
            )
            for a in artifacts
        ]
        
        return ArtifactListResponse(
            artifacts=artifact_responses,
            total_count=len(artifact_responses),
            page=page,
            page_size=page_size
        )
        
    except StorageError as e:
        raise HTTPException(status_code=400, detail=f"Storage error: {e.message}")


@router.get("/artifacts/{artifact_id}/url", response_model=PresignedUrlResponse)
async def get_presigned_url(
    artifact_id: str,
    user_id: Optional[str] = Query(None),
    expires_in: int = Query(3600, ge=60, le=86400),
    permission: AccessPermission = Query(AccessPermission.READ)
):
    """Generate presigned URL for artifact access."""
    try:
        url = await storage_manager.get_artifact_url(
            artifact_id, user_id=user_id, expires_in=expires_in, permission=permission
        )
        
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        return PresignedUrlResponse(
            url=url,
            expires_at=expires_at,
            artifact_id=artifact_id
        )
        
    except StorageError as e:
        raise HTTPException(status_code=400, detail=f"Storage error: {e.message}")


@router.get("/stats", response_model=StorageStatsResponse)
async def get_storage_stats():
    """Get storage statistics."""
    try:
        stats = await storage_manager.get_storage_stats()
        
        return StorageStatsResponse(
            total_operations=stats.get("operations", 0),
            bytes_stored=stats.get("bytes_stored", 0),
            deduplication=stats.get("deduplication", {})
        )
        
    except StorageError as e:
        raise HTTPException(status_code=400, detail=f"Storage error: {e.message}")


@router.post("/cleanup")
async def cleanup_expired_artifacts():
    """Clean up expired artifacts."""
    try:
        cleaned_count = await storage_manager.cleanup_expired_artifacts()
        
        return {
            "message": "Cleanup completed successfully",
            "artifacts_cleaned": cleaned_count
        }
        
    except StorageError as e:
        raise HTTPException(status_code=400, detail=f"Storage error: {e.message}")


@router.get("/health")
async def storage_health_check():
    """Check storage system health."""
    try:
        is_healthy = await storage_manager.health_check()
        
        if not is_healthy:
            raise HTTPException(status_code=503, detail="Storage system unhealthy")
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "backend": storage_manager.config.backend.value
        }
        
    except StorageError as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {e.message}")
