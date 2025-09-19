"""
Proof System Tests - Story 9: Basic Proof Generation
"""

import pytest
import json
import hashlib
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from src.proofs import (
    ProofData, ProofMetadata, ValidationResult, ProofFormat, ProofConfig, 
    ProofError, JSONProofGenerator, ProofGenerator
)


class TestValidationResult:
    """Test validation result data structure."""
    
    def test_validation_result_creation(self):
        """Test creating validation result."""
        result = ValidationResult(
            validator_id="val_123",
            execution_id="exec_456",
            workspace_id="ws_789",
            user_id="user_101",
            input_data={"text": "Hello"},
            output_data={"sentiment": "positive"},
            is_valid=True
        )
        
        assert result.validator_id == "val_123"
        assert result.is_valid is True


class TestProofMetadata:
    """Test proof metadata structure."""
    
    def test_metadata_creation(self):
        """Test creating proof metadata."""
        metadata = ProofMetadata(
            validator_id="val_123",
            execution_id="exec_456"
        )
        
        assert metadata.validator_id == "val_123"
        assert metadata.proof_format == ProofFormat.JSON
        assert len(metadata.proof_id) > 0


class TestProofData:
    """Test proof data structure."""
    
    def test_content_hash_calculation(self):
        """Test SHA-256 content hash calculation."""
        metadata = ProofMetadata()
        validation_result = ValidationResult(
            validator_id="test", execution_id="test", workspace_id="test",
            user_id="test", input_data={}, output_data={}, is_valid=True
        )
        proof_content = {"test": "data"}
        
        proof_data = ProofData(
            metadata=metadata,
            validation_result=validation_result,
            proof_content=proof_content
        )
        
        content_str = json.dumps(proof_content, sort_keys=True, separators=(',', ':'))
        expected_hash = hashlib.sha256(content_str.encode('utf-8')).hexdigest()
        
        calculated_hash = proof_data.calculate_content_hash()
        assert calculated_hash == expected_hash


class TestJSONProofGenerator:
    """Test JSON proof generator."""
    
    @pytest.mark.asyncio
    async def test_generate_proof_basic(self):
        """Test basic proof generation."""
        config = ProofConfig(enable_signing=False)
        generator = JSONProofGenerator(config)
        
        validation_result = ValidationResult(
            validator_id="val_123",
            execution_id="exec_456",
            workspace_id="ws_789",
            user_id="user_101",
            input_data={"text": "test"},
            output_data={"result": "valid"},
            is_valid=True
        )
        
        proof_data = await generator.generate_proof(validation_result)
        
        assert proof_data.proof_id is not None
        assert proof_data.is_valid is True
        assert proof_data.metadata.proof_format == ProofFormat.JSON
        assert proof_data.metadata.content_hash != ""
    
    @pytest.mark.asyncio
    async def test_serialize_proof(self):
        """Test proof serialization."""
        config = ProofConfig(enable_signing=False, enable_compression=False)
        generator = JSONProofGenerator(config)
        
        validation_result = ValidationResult(
            validator_id="test", execution_id="test", workspace_id="test",
            user_id="test", input_data={}, output_data={}, is_valid=True
        )
        
        proof_data = await generator.generate_proof(validation_result)
        serialized = await generator.serialize_proof(proof_data)
        
        assert isinstance(serialized, bytes)
        assert len(serialized) > 0


class TestProofGenerator:
    """Test proof generator orchestrator."""
    
    @pytest.mark.asyncio
    async def test_generate_proof(self):
        """Test proof generation through manager."""
        config = ProofConfig(enable_signing=False)
        generator = ProofGenerator(config)
        
        validation_result = ValidationResult(
            validator_id="val_123",
            execution_id="exec_456",
            workspace_id="ws_789",
            user_id="user_101",
            input_data={"test": True},
            output_data={"valid": True},
            is_valid=True
        )
        
        proof_data = await generator.generate_proof(validation_result)
        
        assert proof_data.proof_id is not None
        assert proof_data.is_valid is True
        assert generator.stats["total_generated"] == 1
        assert generator.stats["successful_generated"] == 1
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test proof generator health check."""
        config = ProofConfig(enable_signing=False)
        generator = ProofGenerator(config)
        
        health = await generator.health_check()
        assert health is True
