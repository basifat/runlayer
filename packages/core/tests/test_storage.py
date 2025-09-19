"""
Storage System Tests - Story 8: Artifact Storage System
"""

import pytest
import hashlib
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.storage import (
    StorageInterface, StorageConfig, ArtifactMetadata, Artifact, RetentionPolicy,
    StorageBackend, AccessPermission, StorageError, S3StorageBackend,
    ContentAddressedStorage, StorageManager
)


class TestArtifactMetadata:
    """Test artifact metadata."""
    
    def test_metadata_creation(self):
        """Test creating metadata with defaults."""
        metadata = ArtifactMetadata()
        assert metadata.artifact_id is not None
        assert metadata.content_hash == ""
        assert metadata.storage_backend == StorageBackend.S3
    
    def test_metadata_to_dict(self):
        """Test converting metadata to dict."""
        metadata = ArtifactMetadata(workspace_id="ws-123")
        result = metadata.to_dict()
        assert isinstance(result, dict)
        assert result["workspace_id"] == "ws-123"


class TestArtifact:
    """Test artifact functionality."""
    
    def test_artifact_creation(self):
        """Test creating artifact."""
        metadata = ArtifactMetadata(content_length=100)
        artifact = Artifact(metadata=metadata, content=b"test")
        assert artifact.size == 100
    
    def test_hash_calculation(self):
        """Test hash calculation."""
        content = b"test content"
        expected = hashlib.sha256(content).hexdigest()
        
        metadata = ArtifactMetadata()
        artifact = Artifact(metadata=metadata, content=content)
        assert artifact.calculate_hash() == expected
    
    def test_expiration_check(self):
        """Test expiration checking."""
        # Not expired
        metadata = ArtifactMetadata(expires_at=datetime.utcnow() + timedelta(hours=1))
        artifact = Artifact(metadata=metadata)
        assert not artifact.is_expired
        
        # Expired
        metadata.expires_at = datetime.utcnow() - timedelta(hours=1)
        assert artifact.is_expired


class TestStorageConfig:
    """Test storage configuration."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = StorageConfig()
        assert config.backend == StorageBackend.S3
        assert config.bucket_name == "runlayer-artifacts"
        assert config.encryption_enabled is True
    
    def test_config_to_dict(self):
        """Test config serialization."""
        config = StorageConfig(access_key_id="test", secret_access_key="secret")
        result = config.to_dict()
        assert result["access_key_id"] == "test"
        assert result["secret_access_key"] == "***"  # Masked


@pytest.fixture
def mock_s3_client():
    """Mock S3 client."""
    client = Mock()
    client.put_object.return_value = {"ETag": "test"}
    client.head_bucket.return_value = {}
    return client


class TestS3StorageBackend:
    """Test S3 storage backend."""
    
    @patch('src.storage.s3_storage.BOTO3_AVAILABLE', True)
    @patch('src.storage.s3_storage.boto3')
    def test_initialization(self, mock_boto3, mock_s3_client):
        """Test S3 backend initialization."""
        mock_boto3.client.return_value = mock_s3_client
        
        config = StorageConfig(bucket_name="test-bucket")
        backend = S3StorageBackend(config)
        
        assert backend.bucket_name == "test-bucket"
        assert backend.client == mock_s3_client
    
    @patch('src.storage.s3_storage.BOTO3_AVAILABLE', False)
    def test_missing_dependency(self):
        """Test missing boto3 dependency."""
        with pytest.raises(StorageError) as exc:
            S3StorageBackend(StorageConfig())
        assert exc.value.error_code == "DEPENDENCY_MISSING"
    
    @patch('src.storage.s3_storage.BOTO3_AVAILABLE', True)
    @patch('src.storage.s3_storage.boto3')
    @pytest.mark.asyncio
    async def test_health_check(self, mock_boto3, mock_s3_client):
        """Test health check."""
        mock_boto3.client.return_value = mock_s3_client
        backend = S3StorageBackend(StorageConfig())
        
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_executor = Mock()
            mock_executor.run_in_executor = AsyncMock(return_value=None)
            mock_loop.return_value = mock_executor
            
            result = await backend.health_check()
            assert result is True


class TestContentAddressedStorage:
    """Test content-addressed storage."""
    
    @pytest.fixture
    def mock_backend(self):
        """Mock storage backend."""
        backend = Mock(spec=StorageBackend)
        backend.store_artifact = AsyncMock()
        backend.retrieve_by_hash = AsyncMock(return_value=None)
        backend.delete_artifact = AsyncMock(return_value=True)
        return backend
    
    def test_initialization(self, mock_backend):
        """Test content store initialization."""
        store = ContentAddressedStorage(mock_backend)
        assert store.backend == mock_backend
        assert store.content_index == {}
        assert store.reference_counts == {}
    
    @pytest.mark.asyncio
    async def test_deduplication_stats(self, mock_backend):
        """Test deduplication statistics."""
        store = ContentAddressedStorage(mock_backend)
        store.content_index = {"hash1": ["art1", "art2"], "hash2": ["art3"]}
        store.reference_counts = {"hash1": 2, "hash2": 1}
        
        stats = await store.get_deduplication_stats()
        
        assert stats["total_artifacts"] == 3
        assert stats["unique_content_items"] == 2
        assert stats["deduplication_ratio"] > 0


class TestStorageManager:
    """Test storage manager."""
    
    @patch('src.storage.manager.S3StorageBackend')
    def test_initialization(self, mock_s3_backend):
        """Test manager initialization."""
        config = StorageConfig()
        manager = StorageManager(config)
        
        assert manager.config == config
        assert isinstance(manager.stats, dict)
        mock_s3_backend.assert_called_once_with(config)
    
    def test_unsupported_backend(self):
        """Test unsupported backend error."""
        # Create config with invalid backend
        config = StorageConfig()
        config.backend = "unsupported"  # Set invalid backend
        
        with pytest.raises(StorageError) as exc:
            StorageManager(config)
        assert exc.value.error_code == "UNSUPPORTED_BACKEND"
    
    @patch('src.storage.manager.S3StorageBackend')
    @pytest.mark.asyncio
    async def test_health_check(self, mock_s3_backend):
        """Test manager health check."""
        mock_backend = Mock()
        mock_backend.health_check = AsyncMock(return_value=True)
        mock_s3_backend.return_value = mock_backend
        
        manager = StorageManager(StorageConfig())
        result = await manager.health_check()
        
        assert result is True
        mock_backend.health_check.assert_called_once()


@pytest.mark.asyncio
async def test_store_artifact_workflow():
    """Test complete artifact storage workflow."""
    # Mock backend for testing
    mock_backend = Mock(spec=StorageInterface)
    mock_backend.store_artifact = AsyncMock()
    mock_backend.retrieve_by_hash = AsyncMock(return_value=None)
    mock_backend.health_check = AsyncMock(return_value=True)
    
    # Create content store
    content_store = ContentAddressedStorage(mock_backend)
    
    # Test content
    content = b"test artifact content"
    metadata = ArtifactMetadata(
        workspace_id="ws-123",
        owner_id="user-456"
    )
    
    # Mock successful storage
    expected_artifact = Artifact(metadata=metadata, content=content)
    mock_backend.store_artifact.return_value = expected_artifact
    
    # Store artifact (first time - no deduplication)
    result = await content_store.store_with_deduplication(content, metadata)
    
    # Verify calls - should store new artifact
    mock_backend.store_artifact.assert_called_once()
    assert result == expected_artifact
    
    # Verify content hash was set
    assert metadata.content_hash != ""


@pytest.mark.asyncio
async def test_artifact_deduplication():
    """Test artifact deduplication functionality."""
    mock_backend = Mock(spec=StorageInterface)
    mock_backend.retrieve_by_hash = AsyncMock()
    
    content_store = ContentAddressedStorage(mock_backend)
    content = b"duplicate content"
    
    # First storage - no existing content
    metadata1 = ArtifactMetadata(artifact_id="art-1")
    mock_backend.retrieve_by_hash.return_value = None
    mock_backend.store_artifact = AsyncMock(return_value=Artifact(metadata=metadata1, content=content))
    
    result1 = await content_store.store_with_deduplication(content, metadata1)
    
    # Second storage - existing content (deduplication)
    metadata2 = ArtifactMetadata(artifact_id="art-2")
    existing_artifact = Artifact(metadata=metadata1, content=content)
    mock_backend.retrieve_by_hash.return_value = existing_artifact
    
    result2 = await content_store.store_with_deduplication(content, metadata2)
    
    # Verify deduplication occurred
    assert mock_backend.store_artifact.call_count == 1  # Only called once
    assert result2.content == content  # Content preserved


def test_storage_error_creation():
    """Test storage error with details."""
    error = StorageError(
        "Test error message",
        error_code="TEST_ERROR",
        details={"key": "value"}
    )
    
    assert str(error) == "Test error message"
    assert error.error_code == "TEST_ERROR"
    assert error.details == {"key": "value"}


def test_retention_policy_validation():
    """Test retention policy validation."""
    policy = RetentionPolicy(
        default_retention_days=30,
        max_retention_days=365,
        min_retention_days=1
    )
    
    assert policy.default_retention_days == 30
    assert policy.max_retention_days == 365
    assert policy.min_retention_days == 1
    
    # Test dictionary conversion
    policy_dict = policy.to_dict()
    assert policy_dict["default_retention_days"] == 30
