"""
Tests for storage components - LocalProofLake and CloudSync.
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock, Mock
from datetime import datetime, timedelta

from runlayer.storage.local import LocalProofLake
from runlayer.storage.sync import CloudSync
from runlayer.models.proof import RunProof, ProofStatus


class TestLocalProofLake:
    """Test LocalProofLake SQLite storage."""
    
    def test_initialization(self, temp_dir):
        """Test LocalProofLake initialization."""
        db_path = temp_dir / "test.db"
        storage = LocalProofLake(db_path)
        
        assert storage.db_path == db_path
        assert db_path.exists()
    
    def test_store_and_get_proof(self, local_storage, sample_proof_data):
        """Test storing and retrieving proofs."""
        proof = RunProof.create_proof(**sample_proof_data)
        
        # Store proof
        success = local_storage.store_proof(proof)
        assert success == True
        
        # Retrieve proof
        retrieved = local_storage.get_proof(proof.id)
        assert retrieved is not None
        assert retrieved.id == proof.id
        assert retrieved.validator_name == proof.validator_name
        assert retrieved.input_data == proof.input_data
        assert retrieved.output_data == proof.output_data
    
    def test_get_nonexistent_proof(self, local_storage):
        """Test retrieving non-existent proof."""
        proof = local_storage.get_proof("nonexistent-id")
        assert proof is None
    
    def test_find_proof_by_input_hash(self, local_storage, sample_proof_data):
        """Test finding proof by input hash."""
        proof = RunProof.create_proof(**sample_proof_data)
        local_storage.store_proof(proof)
        
        # Find by input hash
        found = local_storage.find_proof_by_input_hash(
            proof.validator_name,
            proof.validator_version,
            proof.input_hash
        )
        
        assert found is not None
        assert found.id == proof.id
        
        # Test with non-existent hash
        not_found = local_storage.find_proof_by_input_hash(
            "nonexistent",
            "1.0.0",
            "fake-hash"
        )
        assert not_found is None
    
    def test_list_proofs(self, local_storage):
        """Test listing proofs with filtering."""
        workspace_id = "test-workspace"
        
        # Create multiple proofs
        proofs = []
        for i in range(5):
            proof = RunProof.create_proof(
                validator_name=f"validator_{i % 2}",  # alternating names
                validator_version="1.0.0",
                input_data={"x": i},
                output_data=i > 2,
                execution_time_ms=i * 10,
                workspace_id=workspace_id
            )
            proofs.append(proof)
            local_storage.store_proof(proof)
        
        # Test listing all proofs
        all_proofs = local_storage.list_proofs(workspace_id=workspace_id)
        assert len(all_proofs) == 5
        
        # Test filtering by validator name
        validator_0_proofs = local_storage.list_proofs(
            workspace_id=workspace_id,
            validator_name="validator_0"
        )
        assert len(validator_0_proofs) == 3  # indices 0, 2, 4
        
        # Test limit and offset
        limited = local_storage.list_proofs(workspace_id=workspace_id, limit=2)
        assert len(limited) == 2
        
        offset = local_storage.list_proofs(workspace_id=workspace_id, limit=2, offset=2)
        assert len(offset) == 2
    
    def test_unsynced_proofs(self, local_storage):
        """Test getting unsynced proofs."""
        workspace_id = "test-workspace"
        
        # Create proofs
        proofs = []
        for i in range(3):
            proof = RunProof.create_proof(
                validator_name="test_validator",
                validator_version="1.0.0",
                input_data={"x": i},
                output_data=True,
                execution_time_ms=10,
                workspace_id=workspace_id
            )
            proofs.append(proof)
            local_storage.store_proof(proof)
        
        # All should be unsynced initially
        unsynced = local_storage.get_unsynced_proofs(workspace_id)
        assert len(unsynced) == 3
        
        # Mark one as synced
        local_storage.mark_proof_synced(proofs[0].id)
        
        # Should have 2 unsynced now
        unsynced = local_storage.get_unsynced_proofs(workspace_id)
        assert len(unsynced) == 2
        
        # Check the synced proof
        synced_proof = local_storage.get_proof(proofs[0].id)
        assert synced_proof.synced_to_cloud == True
        assert synced_proof.sync_timestamp is not None
    
    def test_mark_proof_synced(self, local_storage, sample_proof_data):
        """Test marking proof as synced."""
        proof = RunProof.create_proof(**sample_proof_data)
        local_storage.store_proof(proof)
        
        # Initially not synced
        assert proof.synced_to_cloud == False
        
        # Mark as synced
        success = local_storage.mark_proof_synced(proof.id)
        assert success == True
        
        # Verify sync status
        synced_proof = local_storage.get_proof(proof.id)
        assert synced_proof.synced_to_cloud == True
        assert synced_proof.sync_timestamp is not None
    
    def test_get_stats(self, local_storage):
        """Test getting storage statistics."""
        workspace_id = "test-workspace"
        
        # Initially no stats
        stats = local_storage.get_stats(workspace_id)
        assert stats["total_proofs"] == 0
        assert stats["synced_proofs"] == 0
        
        # Add proofs
        for i in range(3):
            proof = RunProof.create_proof(
                validator_name=f"validator_{i % 2}",
                validator_version="1.0.0",
                input_data={"x": i},
                output_data=True,
                execution_time_ms=10,
                workspace_id=workspace_id
            )
            local_storage.store_proof(proof)
        
        # Mark one as synced
        proofs = local_storage.list_proofs(workspace_id=workspace_id)
        local_storage.mark_proof_synced(proofs[0].id)
        
        # Check stats
        stats = local_storage.get_stats(workspace_id)
        assert stats["total_proofs"] == 3
        assert stats["synced_proofs"] == 1
        assert stats["pending_sync"] == 2
        assert stats["unique_validators"] == 2
        assert stats["storage_size_mb"] >= 0
    
    def test_cleanup_old_proofs(self, local_storage):
        """Test cleaning up old proofs."""
        workspace_id = "test-workspace"
        
        # Create proofs (all recent, so won't be cleaned)
        for i in range(3):
            proof = RunProof.create_proof(
                validator_name="test_validator",
                validator_version="1.0.0",
                input_data={"x": i},
                output_data=True,
                execution_time_ms=10,
                workspace_id=workspace_id
            )
            local_storage.store_proof(proof)
            # Mark as synced so they're eligible for cleanup
            local_storage.mark_proof_synced(proof.id)
        
        # Try to cleanup (should return 0 since proofs are recent)
        cleaned = local_storage.cleanup_old_proofs(workspace_id, days=1)
        assert cleaned == 0
        
        # All proofs should still exist
        proofs = local_storage.list_proofs(workspace_id=workspace_id)
        assert len(proofs) == 3


class TestCloudSync:
    """Test CloudSync functionality."""
    
    @pytest.fixture
    def mock_workspace(self, test_workspace):
        """Mock workspace for cloud sync tests."""
        return test_workspace
    
    @pytest.fixture
    def cloud_sync(self, mock_workspace, local_storage):
        """Create CloudSync instance for testing."""
        return CloudSync(mock_workspace, local_storage, "https://api.test.com")
    
    @pytest.mark.asyncio
    async def test_initialization(self, cloud_sync):
        """Test CloudSync initialization."""
        assert cloud_sync.api_base_url == "https://api.test.com"
        assert cloud_sync.workspace is not None
        assert cloud_sync.local_storage is not None
    
    @pytest.mark.asyncio
    async def test_authentication_success(self, cloud_sync):
        """Test successful authentication."""
        # Create a proper mock response that behaves like httpx.Response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test-token",
            "refresh_token": "test-refresh",
            "expires_in": 900
        }
        mock_response.text = ""
        
        # Mock the client directly on the cloud_sync instance
        cloud_sync._client = AsyncMock()
        cloud_sync._client.post.return_value = mock_response
        
        success = await cloud_sync.authenticate()
        
        assert success == True
        assert cloud_sync._access_token == "test-token"
        assert cloud_sync._refresh_token == "test-refresh"
        assert cloud_sync._token_expires_at is not None
    
    @pytest.mark.asyncio
    async def test_authentication_failure(self, cloud_sync):
        """Test failed authentication."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        
        # Mock the client directly
        cloud_sync._client = AsyncMock()
        cloud_sync._client.post.return_value = mock_response
        
        success = await cloud_sync.authenticate()
        
        assert success == False
        assert cloud_sync._access_token is None
    
    @pytest.mark.asyncio
    async def test_sync_proofs_no_auth(self, cloud_sync):
        """Test sync proofs without authentication."""
        # Mock failed authentication
        cloud_sync._client = AsyncMock()
        cloud_sync._client.post.return_value = AsyncMock(status_code=401)
        
        result = await cloud_sync.sync_proofs()
        
        assert result["success"] == False
        assert "Authentication failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_sync_proofs_no_proofs(self, cloud_sync, local_storage):
        """Test sync proofs when no proofs to sync."""
        # Mock successful authentication
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "test-token",
            "expires_in": 900
        }
        
        cloud_sync._client = AsyncMock()
        cloud_sync._client.post.return_value = mock_auth_response
        
        result = await cloud_sync.sync_proofs()
        
        assert result["success"] == True
        assert result["synced_count"] == 0
        assert "No proofs to sync" in result["message"]
    
    @pytest.mark.asyncio
    async def test_sync_proofs_success(self, cloud_sync, local_storage):
        """Test successful proof synchronization."""
        # Create unsynced proofs
        workspace_id = cloud_sync.workspace.id
        for i in range(2):
            proof = RunProof.create_proof(
                validator_name="test_validator",
                validator_version="1.0.0",
                input_data={"x": i},
                output_data=True,
                execution_time_ms=10,
                workspace_id=workspace_id
            )
            local_storage.store_proof(proof)
        
        # Mock successful authentication and sync
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "test-token",
            "expires_in": 900
        }
        
        mock_sync_response = Mock()
        mock_sync_response.status_code = 201
        
        cloud_sync._client = AsyncMock()
        cloud_sync._client.post.side_effect = [mock_auth_response, mock_sync_response]
        
        result = await cloud_sync.sync_proofs()
        
        assert result["success"] == True
        assert result["synced_count"] == 2
        assert result["failed_count"] == 0
        
        # Verify proofs were marked as synced
        unsynced = local_storage.get_unsynced_proofs(workspace_id)
        assert len(unsynced) == 0
    
    @pytest.mark.asyncio
    async def test_sync_proofs_conflict_resolution(self, cloud_sync, local_storage):
        """Test sync with conflict resolution."""
        # Create unsynced proof
        workspace_id = cloud_sync.workspace.id
        proof = RunProof.create_proof(
            validator_name="test_validator",
            validator_version="1.0.0",
            input_data={"x": 1},
            output_data=True,
            execution_time_ms=10,
            workspace_id=workspace_id
        )
        local_storage.store_proof(proof)
        
        # Mock authentication and conflict response
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "test-token",
            "expires_in": 900
        }
        
        mock_conflict_response = Mock()
        mock_conflict_response.status_code = 409
        mock_conflict_response.json.return_value = {
            "existing_proof_ids": [proof.id]
        }
        
        cloud_sync._client = AsyncMock()
        cloud_sync._client.post.side_effect = [mock_auth_response, mock_conflict_response]
        
        result = await cloud_sync.sync_proofs()
        
        assert result["synced_count"] == 1  # Marked as synced due to conflict
        assert result["failed_count"] == 0
        
        # Verify proof was marked as synced
        synced_proof = local_storage.get_proof(proof.id)
        assert synced_proof.synced_to_cloud == True
    
    @pytest.mark.asyncio
    async def test_test_connection(self, cloud_sync):
        """Test connection testing."""
        mock_response = Mock()
        mock_response.status_code = 200
        
        cloud_sync._client = AsyncMock()
        cloud_sync._client.get.return_value = mock_response
        
        result = await cloud_sync.test_connection()
        
        assert result == True
    
    @pytest.mark.asyncio
    async def test_download_proofs(self, cloud_sync):
        """Test downloading proofs from cloud."""
        # Mock successful authentication and download
        mock_auth_response = Mock()
        mock_auth_response.status_code = 200
        mock_auth_response.json.return_value = {
            "access_token": "test-token",
            "expires_in": 900
        }
        
        mock_download_response = Mock()
        mock_download_response.status_code = 200
        mock_download_response.json.return_value = {
            "proofs": [
                {
                    "id": "test-proof-1",
                    "validator_name": "cloud_validator",
                    "validator_version": "1.0.0",
                    "input_hash": "hash1",
                    "output_hash": "hash2",
                    "input_data": {"x": 1},
                    "output_data": True,
                    "execution_time_ms": 10,
                    "status": "validated",
                    "created_at": datetime.utcnow().isoformat(),
                    "workspace_id": "test-workspace",
                    "synced_to_cloud": True,
                    "metadata": {}
                }
            ]
        }
        
        cloud_sync._client = AsyncMock()
        cloud_sync._client.post.return_value = mock_auth_response
        cloud_sync._client.get.return_value = mock_download_response
        
        proofs = await cloud_sync.download_proofs()
        
        assert len(proofs) == 1
        assert proofs[0].id == "test-proof-1"
        assert proofs[0].validator_name == "cloud_validator"
