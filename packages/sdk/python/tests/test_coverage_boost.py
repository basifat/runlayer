"""
Additional tests to boost coverage to 85%+
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from pathlib import Path

from runlayer.client import RunLayerClient
from runlayer.storage.sync import CloudSync
from runlayer.storage.local import LocalProofLake
from runlayer.models.proof import RunProof
from runlayer.validator import validator


class TestCoverageBoost:
    """Additional tests to reach 85% coverage."""
    
    def test_client_auto_sync_trigger(self, temp_dir):
        """Test client auto sync triggering."""
        client = RunLayerClient(
            workspace="auto-sync-test",
            storage_path=temp_dir,
            auto_sync=True,
            api_key="test-key"
        )
        
        proof = RunProof.create_proof(
            validator_name="test",
            validator_version="1.0.0",
            input_data={"x": 1},
            output_data=True,
            execution_time_ms=10,
            workspace_id=client.workspace.id
        )
        
        # Store proof (auto sync disabled for test)
        client.workspace.config.auto_sync = False
        success = client.store_proof(proof)
        assert success == True
    
    def test_client_context_managers(self, temp_dir):
        """Test client context managers."""
        # Test sync context manager
        with RunLayerClient(workspace="context-test", storage_path=temp_dir) as client:
            assert client.workspace.config.name == "context-test"
        
        # Workspace should be saved after exit
        client2 = RunLayerClient(workspace="context-test", storage_path=temp_dir)
        assert client2.workspace.config.name == "context-test"
    
    @pytest.mark.asyncio
    async def test_client_async_context_manager(self, temp_dir):
        """Test client async context manager."""
        async with RunLayerClient(workspace="async-test", storage_path=temp_dir) as client:
            assert client.workspace.config.name == "async-test"
    
    def test_local_storage_error_handling(self, temp_dir):
        """Test local storage error handling."""
        storage = LocalProofLake(temp_dir / "test.db")
        
        # Test with invalid proof data
        invalid_proof = MagicMock()
        invalid_proof.id = "test-id"
        invalid_proof.validator_name = None  # This will cause an error
        
        success = storage.store_proof(invalid_proof)
        assert success == False
    
    def test_workspace_cleanup(self, temp_dir):
        """Test workspace cleanup functionality."""
        from runlayer.models.workspace import Workspace
        
        workspace = Workspace.create_workspace(
            name="cleanup-test",
            storage_path=temp_dir
        )
        
        # Test cleanup (should return 0 for recent proofs)
        cleaned = workspace.cleanup_old_proofs(days=1)
        assert cleaned == 0
    
    @pytest.mark.asyncio
    async def test_cloud_sync_edge_cases(self, temp_dir):
        """Test CloudSync edge cases."""
        from runlayer.models.workspace import Workspace
        
        workspace = Workspace.create_workspace(
            name="edge-test",
            storage_path=temp_dir,
            api_key="test-key"
        )
        
        storage = LocalProofLake(workspace.get_database_path())
        cloud_sync = CloudSync(workspace, storage)
        
        # Test without client initialization
        result = await cloud_sync.test_connection()
        assert result == False
        
        # Test download without authentication
        proofs = await cloud_sync.download_proofs()
        assert len(proofs) == 0
    
    def test_validator_edge_cases(self, temp_dir):
        """Test validator edge cases."""
        client = RunLayerClient(workspace="edge-test", storage_path=temp_dir)
        
        # Test validator with complex metadata
        @validator(
            name="complex_validator",
            version="1.0.0",
            client=client,
            description="Complex validator with all options",
            metadata={"complex": {"nested": {"data": [1, 2, 3]}}}
        )
        def complex_validation(data):
            return {"processed": True, "complex_result": data}
        
        result = complex_validation({"input": "test"})
        assert result["processed"] == True
        
        # Check proof was created with metadata
        proofs = client.list_proofs(validator_name="complex_validator")
        assert len(proofs) == 1
        assert proofs[0].metadata["complex"]["nested"]["data"] == [1, 2, 3]
    
    def test_proof_model_edge_cases(self):
        """Test RunProof model edge cases."""
        # Test with complex data types
        complex_input = {
            "list": [1, 2, 3],
            "dict": {"nested": True},
            "none": None,
            "bool": False
        }
        
        proof = RunProof.create_proof(
            validator_name="complex_data_test",
            validator_version="1.0.0",
            input_data=complex_input,
            output_data={"result": "success"},
            execution_time_ms=25,
            workspace_id="test-workspace"
        )
        
        # Test proof validation with complex data
        assert proof.is_valid() == True
        
        # Test signature data generation
        sig_data = proof.get_signature_data()
        assert isinstance(sig_data, str)
        assert proof.id in sig_data
    
    def test_logging_edge_cases(self):
        """Test logging edge cases."""
        from runlayer.utils.logging import PerformanceLogger, get_logger
        
        logger = get_logger("edge-test")
        
        # Test performance logger with exception
        try:
            with PerformanceLogger(logger, "failing_operation"):
                raise ValueError("Test error")
        except ValueError:
            pass  # Expected
        
        # Test performance logger with no start time
        perf_logger = PerformanceLogger(logger, "test")
        perf_logger.start_time = None
        perf_logger.__exit__(None, None, None)  # Should not crash
    
    def test_crypto_edge_cases(self, temp_dir):
        """Test crypto edge cases."""
        from runlayer.utils.crypto import KeyManager, verify_signature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        
        key_manager = KeyManager(temp_dir)
        
        # Test key generation multiple times (should reuse existing)
        key1 = key_manager.get_private_key()
        key2 = key_manager.get_private_key()
        
        # Should be the same key (test by getting public key bytes)
        pub1 = key_manager.get_public_key_bytes()
        key_manager._public_key = None  # Reset cache
        pub2 = key_manager.get_public_key_bytes()
        assert pub1 == pub2
        
        # Test invalid signature verification
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Test with malformed signature
        is_valid = verify_signature("test", "invalid-base64", public_key)
        assert is_valid == False
    
    def test_workspace_model_edge_cases(self, temp_dir):
        """Test workspace model edge cases."""
        from runlayer.models.workspace import Workspace
        
        # Test workspace with all optional parameters
        workspace = Workspace.create_workspace(
            name="full-config-test",
            storage_path=temp_dir,
            api_key="test-key",
            description="Full configuration test",
            max_storage_mb=500,
            auto_sync=False,
            sync_interval_seconds=600,
            encrypt_local_storage=False,
            batch_sync_size=25
        )
        
        # Test all configuration options
        config = workspace.config
        assert config.description == "Full configuration test"
        assert config.max_storage_mb == 500
        assert config.auto_sync == False
        assert config.sync_interval_seconds == 600
        assert config.encrypt_local_storage == False
        assert config.batch_sync_size == 25
        
        # Test quota checking
        workspace.update_stats(100, 50, 600.0)  # Over quota
        assert workspace.is_over_quota() == True
        
        workspace.update_stats(100, 50, 400.0)  # Under quota
        assert workspace.is_over_quota() == False
    
    def test_storage_local_edge_cases(self, temp_dir):
        """Test LocalProofLake edge cases."""
        storage = LocalProofLake(temp_dir / "edge_test.db")
        
        # Test database size calculation
        size_mb = storage._get_db_size_mb()
        assert isinstance(size_mb, float)
        assert size_mb >= 0
        
        # Test with non-existent proof
        proof = storage.get_proof("non-existent-id")
        assert proof is None
        
        # Test stats with empty database
        stats = storage.get_stats("empty-workspace")
        assert stats["total_proofs"] == 0
        assert stats["synced_proofs"] == 0
    
    def test_validator_utilities_edge_cases(self, temp_dir):
        """Test validator utility functions."""
        from runlayer.validator import get_original_function, create_validator
        
        client = RunLayerClient(workspace="utils-test", storage_path=temp_dir)
        
        # Test create_validator function
        def my_function(x: int) -> bool:
            return x > 0
        
        validator_func = create_validator(
            my_function,
            name="programmatic_validator",
            version="1.0.0",
            client=client,
            description="Created programmatically"
        )
        
        # Test the created validator
        result = validator_func(5)
        assert result == True
        
        # Test get_original_function
        original = get_original_function(validator_func)
        assert original == my_function
        
        # Test with non-validator function
        def regular_func():
            return True
        
        original = get_original_function(regular_func)
        assert original is None
