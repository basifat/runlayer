"""
Integration tests for RunLayer SDK - testing end-to-end workflows.
"""

import pytest
import asyncio
from pathlib import Path

from runlayer import validator, RunLayerClient, get_default_client, set_default_client
from runlayer.models.proof import ProofStatus


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""
    
    def test_basic_validator_workflow(self, temp_dir):
        """Test basic validator workflow from decoration to proof storage."""
        # Create client
        client = RunLayerClient(
            workspace="e2e-basic",
            storage_path=temp_dir,
            auto_sync=False
        )
        
        # Create validator
        @validator(name="email_validator", version="1.0.0", client=client)
        def validate_email(email: str) -> bool:
            """Validate email format."""
            return "@" in email and "." in email.split("@")[1]
        
        # Test valid email
        result1 = validate_email("test@example.com")
        assert result1 == True
        
        # Test invalid email
        result2 = validate_email("invalid-email")
        assert result2 == False
        
        # Check proofs were created
        proofs = client.list_proofs(validator_name="email_validator")
        assert len(proofs) == 2
        
        # Check proof details
        valid_proof = next(p for p in proofs if p.output_data == True)
        invalid_proof = next(p for p in proofs if p.output_data == False)
        
        assert valid_proof.input_data["args"] == ["test@example.com"]
        assert invalid_proof.input_data["args"] == ["invalid-email"]
        
        # Check both proofs are signed
        assert valid_proof.signature is not None
        assert invalid_proof.signature is not None
        
        # Check proof integrity
        assert valid_proof.is_valid() == True
        assert invalid_proof.is_valid() == True
    
    def test_caching_workflow(self, temp_dir):
        """Test result caching workflow."""
        client = RunLayerClient(
            workspace="e2e-caching",
            storage_path=temp_dir,
            auto_sync=False
        )
        
        call_count = 0
        
        @validator(name="expensive_validator", version="1.0.0", client=client, cache_results=True)
        def expensive_operation(x: int) -> int:
            """Simulate expensive operation."""
            nonlocal call_count
            call_count += 1
            return x * x
        
        # First call
        result1 = expensive_operation(5)
        assert result1 == 25
        assert call_count == 1
        
        # Second call with same input (should use cache)
        result2 = expensive_operation(5)
        assert result2 == 25
        assert call_count == 1  # Not called again
        
        # Different input (should call function)
        result3 = expensive_operation(10)
        assert result3 == 100
        assert call_count == 2
        
        # Check only 2 proofs created (one for each unique input)
        proofs = client.list_proofs(validator_name="expensive_validator")
        assert len(proofs) == 2
    
    def test_multiple_validators_workflow(self, temp_dir):
        """Test workflow with multiple validators."""
        client = RunLayerClient(
            workspace="e2e-multiple",
            storage_path=temp_dir,
            auto_sync=False
        )
        
        @validator(name="string_validator", version="1.0.0", client=client)
        def validate_string(s: str) -> bool:
            return len(s) >= 3
        
        @validator(name="number_validator", version="1.0.0", client=client)
        def validate_number(n: int) -> bool:
            return n > 0
        
        @validator(name="combined_validator", version="1.0.0", client=client)
        def validate_combined(s: str, n: int) -> dict:
            return {
                "string_valid": validate_string(s),
                "number_valid": validate_number(n),
                "both_valid": validate_string(s) and validate_number(n)
            }
        
        # Test combined validation
        result = validate_combined("hello", 42)
        
        assert result["string_valid"] == True
        assert result["number_valid"] == True
        assert result["both_valid"] == True
        
        # Check all proofs were created
        all_proofs = client.list_proofs()
        assert len(all_proofs) == 3  # One for each validator
        
        # Check specific validators
        string_proofs = client.list_proofs(validator_name="string_validator")
        number_proofs = client.list_proofs(validator_name="number_validator")
        combined_proofs = client.list_proofs(validator_name="combined_validator")
        
        assert len(string_proofs) == 1
        assert len(number_proofs) == 1
        assert len(combined_proofs) == 1
    
    def test_error_handling_workflow(self, temp_dir):
        """Test error handling in validation workflow."""
        client = RunLayerClient(
            workspace="e2e-errors",
            storage_path=temp_dir,
            auto_sync=False
        )
        
        @validator(name="error_validator", version="1.0.0", client=client)
        def validate_with_errors(x: int) -> int:
            if x < 0:
                raise ValueError("Negative numbers not allowed")
            elif x == 0:
                raise ZeroDivisionError("Zero not allowed")
            return x * 2
        
        # Successful validation
        result = validate_with_errors(5)
        assert result == 10
        
        # Error validations
        with pytest.raises(ValueError):
            validate_with_errors(-1)
        
        with pytest.raises(ZeroDivisionError):
            validate_with_errors(0)
        
        # Check all proofs were created (including error proofs)
        proofs = client.list_proofs(validator_name="error_validator")
        assert len(proofs) == 3
        
        # Check error proofs
        error_proofs = [p for p in proofs if p.status == ProofStatus.FAILED]
        assert len(error_proofs) == 2
        
        # Check error proof content
        value_error_proof = next(
            p for p in error_proofs 
            if "Negative numbers not allowed" in str(p.output_data)
        )
        assert value_error_proof is not None
        assert value_error_proof.metadata["execution_status"] == "failed"
    
    def test_workspace_isolation(self, temp_dir):
        """Test workspace isolation between projects."""
        # Create two separate clients
        client1 = RunLayerClient(
            workspace="project1",
            storage_path=temp_dir,
            auto_sync=False
        )
        
        client2 = RunLayerClient(
            workspace="project2",
            storage_path=temp_dir,
            auto_sync=False
        )
        
        # Create validators in each workspace
        @validator(name="validator_a", version="1.0.0", client=client1)
        def validator_a(x: int) -> int:
            return x + 1
        
        @validator(name="validator_b", version="1.0.0", client=client2)
        def validator_b(x: int) -> int:
            return x + 2
        
        # Execute validators
        result1 = validator_a(10)
        result2 = validator_b(10)
        
        assert result1 == 11
        assert result2 == 12
        
        # Check workspace isolation
        proofs1 = client1.list_proofs()
        proofs2 = client2.list_proofs()
        
        # Each workspace should have its own proofs
        # Note: May have more proofs from other tests in same workspace
        validator_a_proofs = client1.list_proofs(validator_name="validator_a")
        validator_b_proofs = client2.list_proofs(validator_name="validator_b")
        
        assert len(validator_a_proofs) == 1
        assert len(validator_b_proofs) == 1
        
        # Proofs should be in different workspaces
        assert proofs1[0].workspace_id != proofs2[0].workspace_id
        assert proofs1[0].workspace_id == client1.workspace.id
        assert proofs2[0].workspace_id == client2.workspace.id
    
    def test_default_client_workflow(self, temp_dir):
        """Test workflow using default client."""
        # Set up default client
        default_client = RunLayerClient(
            workspace="default-test",
            storage_path=temp_dir,
            auto_sync=False
        )
        set_default_client(default_client)
        
        # Create validator without explicit client
        @validator(name="default_validator", version="1.0.0")
        def default_validation(text: str) -> str:
            return text.upper()
        
        # Execute validator
        result = default_validation("hello world")
        assert result == "HELLO WORLD"
        
        # Check proof was created in default client
        proofs = default_client.list_proofs(validator_name="default_validator")
        assert len(proofs) == 1
        
        # Verify it's the same as get_default_client
        current_default = get_default_client()
        assert current_default.workspace.id == default_client.workspace.id
    
    def test_performance_tracking_workflow(self, temp_dir):
        """Test performance tracking in validation workflow."""
        client = RunLayerClient(
            workspace="e2e-performance",
            storage_path=temp_dir,
            auto_sync=False
        )
        
        @validator(name="timed_validator", version="1.0.0", client=client)
        def timed_operation(delay_ms: int) -> str:
            """Operation with controlled delay."""
            import time
            time.sleep(delay_ms / 1000.0)
            return f"Completed after {delay_ms}ms"
        
        # Execute with different delays
        result1 = timed_operation(50)   # 50ms
        result2 = timed_operation(100)  # 100ms
        
        assert "50ms" in result1
        assert "100ms" in result2
        
        # Check execution times were recorded
        proofs = client.list_proofs(validator_name="timed_validator")
        assert len(proofs) == 2
        
        # Sort by creation time
        proofs.sort(key=lambda p: p.created_at)
        
        # Check execution times (allow some variance)
        assert 40 <= proofs[0].execution_time_ms <= 80   # ~50ms
        assert 90 <= proofs[1].execution_time_ms <= 150  # ~100ms
    
    def test_metadata_workflow(self, temp_dir):
        """Test metadata inclusion in validation workflow."""
        client = RunLayerClient(
            workspace="e2e-metadata",
            storage_path=temp_dir,
            auto_sync=False
        )
        
        @validator(
            name="metadata_validator",
            version="2.1.0",
            client=client,
            description="Validator with rich metadata",
            metadata={
                "team": "data-science",
                "environment": "test",
                "category": "validation"
            }
        )
        def rich_validator(data: dict) -> dict:
            """Validator with comprehensive metadata."""
            return {
                "processed": True,
                "item_count": len(data),
                "keys": list(data.keys())
            }
        
        # Execute validator
        test_data = {"name": "test", "value": 123, "active": True}
        result = rich_validator(test_data)
        
        assert result["processed"] == True
        assert result["item_count"] == 3
        assert "name" in result["keys"]
        
        # Check metadata in proof
        proofs = client.list_proofs(validator_name="metadata_validator")
        assert len(proofs) == 1
        
        proof = proofs[0]
        assert proof.metadata["team"] == "data-science"
        assert proof.metadata["environment"] == "test"
        assert proof.metadata["category"] == "validation"
        assert proof.metadata["description"] == "Validator with rich metadata"
        assert "correlation_id" in proof.metadata
        assert proof.metadata["function_name"] == "rich_validator"


class TestWorkspaceManagement:
    """Test workspace management workflows."""
    
    def test_workspace_stats_workflow(self, temp_dir):
        """Test workspace statistics workflow."""
        client = RunLayerClient(
            workspace="stats-test",
            storage_path=temp_dir,
            auto_sync=False
        )
        
        # Initially empty
        stats = client.get_workspace_stats()
        assert stats["total_proofs"] == 0
        assert stats["synced_proofs"] == 0
        
        # Create some validators and execute them
        @validator(name="stats_validator_1", version="1.0.0", client=client)
        def validator1(x: int) -> bool:
            return x > 0
        
        @validator(name="stats_validator_2", version="1.0.0", client=client)
        def validator2(s: str) -> int:
            return len(s)
        
        # Execute validators multiple times
        validator1(5)
        validator1(-3)
        validator2("hello")
        validator2("world")
        validator2("")
        
        # Check updated stats
        stats = client.get_workspace_stats()
        assert stats["total_proofs"] == 5
        assert stats["synced_proofs"] == 0  # No cloud sync
        assert stats["unique_validators"] == 2
        assert stats["workspace_name"] == "stats-test"
        assert "storage_path" in stats
        assert "created_at" in stats
    
    def test_workspace_persistence(self, temp_dir):
        """Test workspace persistence across client instances."""
        workspace_name = "persistence-test"
        
        # Create first client and add some proofs
        client1 = RunLayerClient(
            workspace=workspace_name,
            storage_path=temp_dir,
            auto_sync=False,
            api_key="test-key-1"
        )
        
        @validator(name="persistent_validator", version="1.0.0", client=client1)
        def persistent_validation(x: int) -> int:
            return x * 2
        
        result1 = persistent_validation(21)
        assert result1 == 42
        
        # Create second client with same workspace
        client2 = RunLayerClient(
            workspace=workspace_name,
            storage_path=temp_dir,
            auto_sync=False,
            api_key="test-key-2"  # Different API key
        )
        
        # Should load existing proofs
        proofs = client2.list_proofs()
        assert len(proofs) == 1
        assert proofs[0].validator_name == "persistent_validator"
        assert proofs[0].output_data == 42
        
        # Workspace should have updated API key
        assert client2.workspace.config.api_key == "test-key-2"
        
        # Should share the same workspace ID
        assert client1.workspace.id == client2.workspace.id


@pytest.mark.asyncio
class TestAsyncWorkflows:
    """Test asynchronous workflows."""
    
    async def test_async_context_manager(self, temp_dir):
        """Test async context manager workflow."""
        async with RunLayerClient(
            workspace="async-test",
            storage_path=temp_dir,
            auto_sync=False
        ) as client:
            
            @validator(name="async_validator", version="1.0.0", client=client)
            def async_validation(data: str) -> dict:
                return {"length": len(data), "upper": data.upper()}
            
            result = async_validation("test")
            assert result["length"] == 4
            assert result["upper"] == "TEST"
            
            # Check proof was created
            proofs = client.list_proofs()
            assert len(proofs) == 1
    
    async def test_connection_testing_workflow(self, temp_dir):
        """Test connection testing workflow."""
        client = RunLayerClient(
            workspace="connection-test",
            storage_path=temp_dir,
            api_key="test-key",
            auto_sync=False
        )
        
        # Test connection (should fail without real API)
        is_connected = await client.test_connection()
        # In test environment, this will likely be False
        assert isinstance(is_connected, bool)
