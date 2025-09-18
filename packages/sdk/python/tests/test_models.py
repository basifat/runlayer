"""
Tests for data models - RunProof and Workspace.
"""

import pytest
from datetime import datetime
from pathlib import Path

from runlayer.models.proof import RunProof, ProofStatus
from runlayer.models.workspace import Workspace, WorkspaceConfig


class TestRunProof:
    """Test RunProof model functionality."""
    
    def test_create_proof(self):
        """Test creating a RunProof."""
        proof = RunProof.create_proof(
            validator_name="test_validator",
            validator_version="1.0.0",
            input_data={"email": "test@example.com"},
            output_data=True,
            execution_time_ms=50,
            workspace_id="test-workspace",
            metadata={"env": "test"}
        )
        
        assert proof.validator_name == "test_validator"
        assert proof.validator_version == "1.0.0"
        assert proof.input_data == {"email": "test@example.com"}
        assert proof.output_data == True
        assert proof.execution_time_ms == 50
        assert proof.workspace_id == "test-workspace"
        assert proof.metadata["env"] == "test"
        assert proof.status == ProofStatus.CREATED
        assert proof.synced_to_cloud == False
        assert proof.signature is None
        
        # Check computed fields
        assert proof.id is not None
        assert len(proof.id) == 16  # 16-character hex string
        assert proof.input_hash is not None
        assert len(proof.input_hash) == 64  # SHA-256 hex string
        assert proof.output_hash is not None
        assert len(proof.output_hash) == 64
        assert isinstance(proof.created_at, datetime)
    
    def test_proof_id_generation(self):
        """Test proof ID generation is deterministic."""
        # Same input should generate same ID
        proof1 = RunProof.create_proof(
            validator_name="test",
            validator_version="1.0.0",
            input_data={"x": 1},
            output_data=True,
            execution_time_ms=10,
            workspace_id="workspace"
        )
        
        proof2 = RunProof.create_proof(
            validator_name="test",
            validator_version="1.0.0",
            input_data={"x": 1},
            output_data=False,  # Different output
            execution_time_ms=20,  # Different execution time
            workspace_id="workspace"
        )
        
        # IDs should be the same (based on validator + input hash)
        assert proof1.id == proof2.id
        assert proof1.input_hash == proof2.input_hash
        assert proof1.output_hash != proof2.output_hash  # Different outputs
    
    def test_hash_data_consistency(self):
        """Test data hashing is consistent."""
        data1 = {"name": "test", "value": 123}
        data2 = {"value": 123, "name": "test"}  # Different order
        
        hash1 = RunProof._hash_data(data1)
        hash2 = RunProof._hash_data(data2)
        
        # Should be the same due to sort_keys=True
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex string
    
    def test_proof_validation(self):
        """Test proof integrity validation."""
        proof = RunProof.create_proof(
            validator_name="test_validator",
            validator_version="1.0.0",
            input_data={"x": 1},
            output_data=True,
            execution_time_ms=10,
            workspace_id="test-workspace"
        )
        
        # Valid proof
        assert proof.is_valid() == True
        
        # Tamper with input data
        proof.input_data = {"x": 2}
        assert proof.is_valid() == False
        
        # Restore and tamper with output data
        proof.input_data = {"x": 1}
        proof.output_data = False
        assert proof.is_valid() == False
    
    def test_signature_data(self):
        """Test signature data generation."""
        proof = RunProof.create_proof(
            validator_name="test_validator",
            validator_version="1.0.0",
            input_data={"x": 1},
            output_data=True,
            execution_time_ms=10,
            workspace_id="test-workspace"
        )
        
        signature_data = proof.get_signature_data()
        
        # Should be valid JSON
        import json
        parsed = json.loads(signature_data)
        
        assert parsed["id"] == proof.id
        assert parsed["validator_name"] == proof.validator_name
        assert parsed["validator_version"] == proof.validator_version
        assert parsed["input_hash"] == proof.input_hash
        assert parsed["output_hash"] == proof.output_hash
        assert parsed["workspace_id"] == proof.workspace_id
    
    def test_proof_status_transitions(self):
        """Test proof status transitions."""
        proof = RunProof.create_proof(
            validator_name="test_validator",
            validator_version="1.0.0",
            input_data={"x": 1},
            output_data=True,
            execution_time_ms=10,
            workspace_id="test-workspace"
        )
        
        # Initial status
        assert proof.status == ProofStatus.CREATED
        
        # Mark as synced
        proof.mark_synced()
        assert proof.status == ProofStatus.SYNCED
        assert proof.synced_to_cloud == True
        assert proof.sync_timestamp is not None
        
        # Mark as failed
        proof.mark_failed()
        assert proof.status == ProofStatus.FAILED
    
    def test_proof_to_dict(self):
        """Test proof serialization to dictionary."""
        proof = RunProof.create_proof(
            validator_name="test_validator",
            validator_version="1.0.0",
            input_data={"x": 1},
            output_data=True,
            execution_time_ms=10,
            workspace_id="test-workspace",
            metadata={"env": "test"}
        )
        
        proof_dict = proof.to_dict()
        
        assert isinstance(proof_dict, dict)
        assert proof_dict["validator_name"] == "test_validator"
        assert proof_dict["validator_version"] == "1.0.0"
        assert proof_dict["input_data"] == {"x": 1}
        assert proof_dict["output_data"] == True
        assert proof_dict["metadata"]["env"] == "test"


class TestProofStatus:
    """Test ProofStatus enum."""
    
    def test_proof_status_values(self):
        """Test ProofStatus enum values."""
        assert ProofStatus.CREATED == "created"
        assert ProofStatus.VALIDATED == "validated"
        assert ProofStatus.SYNCED == "synced"
        assert ProofStatus.FAILED == "failed"
    
    def test_proof_status_in_model(self):
        """Test ProofStatus usage in model."""
        proof = RunProof.create_proof(
            validator_name="test",
            validator_version="1.0.0",
            input_data={},
            output_data=True,
            execution_time_ms=10,
            workspace_id="test"
        )
        
        # Can assign enum values
        proof.status = ProofStatus.VALIDATED
        assert proof.status == ProofStatus.VALIDATED
        assert proof.status.value == "validated"


class TestWorkspaceConfig:
    """Test WorkspaceConfig model."""
    
    def test_workspace_config_creation(self, temp_dir):
        """Test creating workspace configuration."""
        config = WorkspaceConfig(
            name="test-workspace",
            storage_path=temp_dir,
            api_key="test-key",
            auto_sync=True,
            max_storage_mb=200
        )
        
        assert config.name == "test-workspace"
        assert config.storage_path == temp_dir
        assert config.api_key == "test-key"
        assert config.auto_sync == True
        assert config.max_storage_mb == 200
        
        # Check defaults
        assert config.sync_interval_seconds == 300
        assert config.api_base_url == "https://api.runlayer.com"
        assert config.max_proof_cache == 1000
        assert config.batch_sync_size == 50
        assert config.encrypt_local_storage == True
    
    def test_workspace_config_defaults(self, temp_dir):
        """Test workspace configuration defaults."""
        config = WorkspaceConfig(
            name="test",
            storage_path=temp_dir
        )
        
        # Check all defaults
        assert config.description is None
        assert config.max_storage_mb == 100
        assert config.auto_sync == True
        assert config.sync_interval_seconds == 300
        assert config.api_base_url == "https://api.runlayer.com"
        assert config.api_key is None
        assert config.max_proof_cache == 1000
        assert config.batch_sync_size == 50
        assert config.encrypt_local_storage == True


class TestWorkspace:
    """Test Workspace model."""
    
    def test_create_workspace(self, temp_dir):
        """Test creating a new workspace."""
        workspace = Workspace.create_workspace(
            name="test-workspace",
            storage_path=temp_dir / "custom",
            api_key="test-key",
            max_storage_mb=200
        )
        
        assert workspace.config.name == "test-workspace"
        assert workspace.config.storage_path == temp_dir / "custom"
        assert workspace.config.api_key == "test-key"
        assert workspace.config.max_storage_mb == 200
        assert workspace.id is not None
        assert len(workspace.id) == 16
        assert workspace.is_active == True
        assert workspace.total_proofs == 0
        assert workspace.synced_proofs == 0
        
        # Check storage directory was created
        assert workspace.config.storage_path.exists()
        assert workspace.config.storage_path.is_dir()
    
    def test_create_workspace_default_path(self):
        """Test creating workspace with default path."""
        workspace = Workspace.create_workspace(name="default-path-test")
        
        expected_path = Path.home() / ".runlayer" / "default-path-test"
        assert workspace.config.storage_path == expected_path
        
        # Cleanup
        import shutil
        if expected_path.exists():
            shutil.rmtree(expected_path)
    
    def test_workspace_save_and_load(self, temp_dir):
        """Test saving and loading workspace."""
        # Create workspace
        workspace = Workspace.create_workspace(
            name="save-load-test",
            storage_path=temp_dir,
            api_key="test-key"
        )
        
        # Save to path
        workspace.save_to_path()
        
        # Load from path
        loaded_workspace = Workspace.load_from_path(temp_dir)
        
        assert loaded_workspace is not None
        assert loaded_workspace.id == workspace.id
        assert loaded_workspace.config.name == workspace.config.name
        assert loaded_workspace.config.api_key == workspace.config.api_key
    
    def test_workspace_load_nonexistent(self, temp_dir):
        """Test loading non-existent workspace."""
        nonexistent_path = temp_dir / "nonexistent"
        workspace = Workspace.load_from_path(nonexistent_path)
        assert workspace is None
    
    def test_workspace_database_path(self, temp_dir):
        """Test workspace database path."""
        workspace = Workspace.create_workspace(
            name="db-path-test",
            storage_path=temp_dir
        )
        
        db_path = workspace.get_database_path()
        expected_path = temp_dir / "prooflake.db"
        assert db_path == expected_path
    
    def test_workspace_update_stats(self, temp_dir):
        """Test updating workspace statistics."""
        workspace = Workspace.create_workspace(
            name="stats-test",
            storage_path=temp_dir
        )
        
        # Update stats
        workspace.update_stats(
            total_proofs=10,
            synced_proofs=7,
            storage_mb=2.5
        )
        
        assert workspace.total_proofs == 10
        assert workspace.synced_proofs == 7
        assert workspace.storage_used_mb == 2.5
    
    def test_workspace_quota_check(self, temp_dir):
        """Test workspace quota checking."""
        workspace = Workspace.create_workspace(
            name="quota-test",
            storage_path=temp_dir,
            max_storage_mb=100
        )
        
        # Under quota
        workspace.update_stats(0, 0, 50.0)
        assert workspace.is_over_quota() == False
        
        # Over quota
        workspace.update_stats(0, 0, 150.0)
        assert workspace.is_over_quota() == True
    
    def test_workspace_sync_status(self, temp_dir):
        """Test workspace sync status."""
        workspace = Workspace.create_workspace(
            name="sync-status-test",
            storage_path=temp_dir,
            api_key="test-key",
            auto_sync=True
        )
        
        workspace.update_stats(10, 6, 1.0)
        workspace.last_sync = datetime.utcnow()
        
        status = workspace.get_sync_status()
        
        assert status["total_proofs"] == 10
        assert status["synced_proofs"] == 6
        assert status["pending_sync"] == 4
        assert status["last_sync"] is not None
        assert status["auto_sync_enabled"] == True
        assert status["has_api_key"] == True
    
    def test_workspace_access_time_update(self, temp_dir):
        """Test workspace access time update."""
        workspace = Workspace.create_workspace(
            name="access-time-test",
            storage_path=temp_dir
        )
        
        original_time = workspace.last_accessed
        
        # Small delay to ensure time difference
        import time
        time.sleep(0.001)
        
        workspace.update_access_time()
        
        assert workspace.last_accessed > original_time
