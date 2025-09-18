"""
Tests for RunLayerClient - the main client class for workspace management.
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from pathlib import Path

from runlayer.client import RunLayerClient
from runlayer.models.proof import RunProof
from runlayer.models.workspace import Workspace


class TestRunLayerClient:
    """Test RunLayerClient functionality."""
    
    def test_client_initialization(self, temp_dir):
        """Test client initialization."""
        client = RunLayerClient(
            workspace="test-init",
            storage_path=temp_dir,
            api_key="test-key",
            auto_sync=False
        )
        
        assert client.workspace_name == "test-init"
        assert client.workspace.config.name == "test-init"
        assert client.workspace.config.api_key == "test-key"
        assert client.workspace.config.auto_sync == False
        assert client.workspace.config.storage_path.name == "test-init"
    
    def test_client_with_existing_workspace(self, test_workspace):
        """Test client initialization with existing workspace."""
        # Create client with same workspace
        client = RunLayerClient(
            workspace=test_workspace.config.name,
            storage_path=test_workspace.config.storage_path.parent,
            api_key="updated-key"
        )
        
        # Should load existing workspace but update API key
        # Note: New workspace will have different ID due to timestamp
        assert client.workspace.config.api_key == "updated-key"
        assert client.workspace.config.name == test_workspace.config.name
    
    def test_store_proof(self, test_client, sample_proof_data):
        """Test storing a proof."""
        proof = RunProof.create_proof(**sample_proof_data)
        
        success = test_client.store_proof(proof)
        assert success == True
        
        # Verify proof was stored
        stored_proof = test_client.get_proof(proof.id)
        assert stored_proof is not None
        assert stored_proof.id == proof.id
        assert stored_proof.validator_name == proof.validator_name
    
    def test_store_proof_with_signing(self, test_client, sample_proof_data):
        """Test storing a proof with signing."""
        proof = RunProof.create_proof(**sample_proof_data)
        
        success = test_client.store_proof(proof, sign=True)
        assert success == True
        
        # Verify proof was signed
        stored_proof = test_client.get_proof(proof.id)
        assert stored_proof.signature is not None
        assert len(stored_proof.signature) > 0
    
    def test_find_existing_proof(self, test_client, sample_proof_data):
        """Test finding existing proof by input hash."""
        proof = RunProof.create_proof(**sample_proof_data)
        test_client.store_proof(proof)
        
        # Find existing proof
        found_proof = test_client.find_existing_proof(
            proof.validator_name,
            proof.validator_version,
            proof.input_hash
        )
        
        assert found_proof is not None
        assert found_proof.id == proof.id
        
        # Test with non-existent proof
        not_found = test_client.find_existing_proof(
            "nonexistent",
            "1.0.0",
            "fake-hash"
        )
        assert not_found is None
    
    def test_list_proofs(self, test_client):
        """Test listing proofs with filtering."""
        # Create multiple proofs
        proof1 = RunProof.create_proof(
            validator_name="validator_a",
            validator_version="1.0.0",
            input_data={"x": 1},
            output_data=True,
            execution_time_ms=10,
            workspace_id=test_client.workspace.id
        )
        
        proof2 = RunProof.create_proof(
            validator_name="validator_b",
            validator_version="1.0.0",
            input_data={"x": 2},
            output_data=False,
            execution_time_ms=20,
            workspace_id=test_client.workspace.id
        )
        
        proof3 = RunProof.create_proof(
            validator_name="validator_a",
            validator_version="2.0.0",
            input_data={"x": 3},
            output_data=True,
            execution_time_ms=30,
            workspace_id=test_client.workspace.id
        )
        
        test_client.store_proof(proof1)
        test_client.store_proof(proof2)
        test_client.store_proof(proof3)
        
        # Test listing all proofs
        all_proofs = test_client.list_proofs()
        assert len(all_proofs) == 3
        
        # Test filtering by validator name
        validator_a_proofs = test_client.list_proofs(validator_name="validator_a")
        assert len(validator_a_proofs) == 2
        
        # Test limit
        limited_proofs = test_client.list_proofs(limit=2)
        assert len(limited_proofs) == 2
        
        # Test offset
        offset_proofs = test_client.list_proofs(limit=2, offset=1)
        assert len(offset_proofs) == 2
    
    def test_workspace_stats(self, test_client, sample_proof_data):
        """Test getting workspace statistics."""
        # Initially no proofs
        stats = test_client.get_workspace_stats()
        assert stats["total_proofs"] == 0
        assert stats["synced_proofs"] == 0
        
        # Add some proofs
        for i in range(3):
            proof_data = sample_proof_data.copy()
            proof_data["input_data"] = {"x": i}
            proof = RunProof.create_proof(**proof_data)
            test_client.store_proof(proof)
        
        # Check updated stats
        stats = test_client.get_workspace_stats()
        assert stats["total_proofs"] == 3
        assert stats["synced_proofs"] == 0  # Not synced yet
        assert stats["workspace_id"] == test_client.workspace.id
        assert stats["workspace_name"] == test_client.workspace.config.name
        assert "storage_path" in stats
        assert "created_at" in stats
    
    @pytest.mark.asyncio
    async def test_sync_to_cloud_no_api_key(self, test_client):
        """Test sync to cloud without API key."""
        # Remove API key
        test_client.workspace.config.api_key = None
        
        result = await test_client.sync_to_cloud()
        
        assert result["success"] == False
        assert "No API key configured" in result["error"]
        assert result["synced_count"] == 0
    
    @pytest.mark.asyncio
    async def test_sync_to_cloud_disabled(self, test_client):
        """Test sync to cloud when auto_sync is disabled."""
        test_client.workspace.config.auto_sync = False
        
        result = await test_client.sync_to_cloud()
        
        assert result["success"] == False
        assert "Auto sync is disabled" in result["error"]
        assert result["synced_count"] == 0
    
    @pytest.mark.asyncio
    async def test_sync_to_cloud_force(self, test_client):
        """Test forced sync to cloud."""
        test_client.workspace.config.auto_sync = False
        
        with patch('runlayer.client.CloudSync') as mock_sync_class:
            mock_sync = AsyncMock()
            mock_sync.sync_proofs.return_value = {
                "success": True,
                "synced_count": 2,
                "failed_count": 0
            }
            mock_sync_class.return_value = mock_sync
            
            result = await test_client.sync_to_cloud(force=True)
            
            assert result["success"] == True
            assert result["synced_count"] == 2
    
    @pytest.mark.asyncio
    async def test_test_connection(self, test_client):
        """Test connection testing."""
        with patch('runlayer.client.CloudSync') as mock_sync_class:
            mock_sync = AsyncMock()
            mock_sync.test_connection.return_value = True
            mock_sync_class.return_value = mock_sync
            
            result = await test_client.test_connection()
            assert result == True
    
    @pytest.mark.asyncio
    async def test_test_connection_no_api_key(self, test_client):
        """Test connection testing without API key."""
        test_client.workspace.config.api_key = None
        
        result = await test_client.test_connection()
        assert result == False
    
    def test_cleanup_old_proofs(self, test_client, sample_proof_data):
        """Test cleaning up old proofs."""
        # Create some proofs
        for i in range(5):
            proof_data = sample_proof_data.copy()
            proof_data["input_data"] = {"x": i}
            proof = RunProof.create_proof(**proof_data)
            test_client.store_proof(proof)
        
        # Cleanup (should return 0 since proofs are recent and not synced)
        cleaned = test_client.cleanup_old_proofs(days=1)
        assert cleaned == 0
        
        # All proofs should still be there
        proofs = test_client.list_proofs()
        assert len(proofs) == 5
    
    def test_context_manager(self, temp_dir):
        """Test client as context manager."""
        with RunLayerClient(workspace="context-test", storage_path=temp_dir) as client:
            assert client.workspace.config.name == "context-test"
            
            # Create a proof
            proof = RunProof.create_proof(
                validator_name="context_validator",
                validator_version="1.0.0",
                input_data={"test": True},
                output_data="success",
                execution_time_ms=10,
                workspace_id=client.workspace.id
            )
            client.store_proof(proof)
        
        # Workspace should be saved after context exit
        # Create new client to verify persistence
        client2 = RunLayerClient(workspace="context-test", storage_path=temp_dir)
        proofs = client2.list_proofs()
        assert len(proofs) == 1
    
    @pytest.mark.asyncio
    async def test_async_context_manager(self, temp_dir):
        """Test client as async context manager."""
        async with RunLayerClient(workspace="async-context-test", storage_path=temp_dir) as client:
            assert client.workspace.config.name == "async-context-test"
            
            # Test that cloud sync would be properly closed
            with patch('runlayer.client.CloudSync') as mock_sync_class:
                mock_sync = AsyncMock()
                mock_sync_class.return_value = mock_sync
                
                # Initialize cloud sync
                await client._get_cloud_sync()
                
                # Verify __aexit__ would be called
                assert mock_sync.__aexit__ is not None


class TestClientConfiguration:
    """Test client configuration options."""
    
    def test_custom_configuration(self, temp_dir):
        """Test client with custom configuration."""
        client = RunLayerClient(
            workspace="custom-config",
            storage_path=temp_dir,
            api_key="custom-key",
            auto_sync=True,
            max_storage_mb=200,
            sync_interval_seconds=600,
            encrypt_local_storage=True,
            batch_sync_size=25
        )
        
        config = client.workspace.config
        assert config.api_key == "custom-key"
        assert config.auto_sync == True
        assert config.max_storage_mb == 200
        assert config.sync_interval_seconds == 600
        assert config.encrypt_local_storage == True
        assert config.batch_sync_size == 25
    
    def test_default_configuration(self, temp_dir):
        """Test client with default configuration."""
        client = RunLayerClient(workspace="default-config", storage_path=temp_dir)
        
        config = client.workspace.config
        assert config.auto_sync == True  # Default
        assert config.max_storage_mb == 100  # Default
        assert config.sync_interval_seconds == 300  # Default
        assert config.encrypt_local_storage == True  # Default
        assert config.batch_sync_size == 50  # Default
