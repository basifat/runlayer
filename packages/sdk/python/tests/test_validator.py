"""
Tests for the @validator decorator - the core feature of RunLayer SDK.
"""

import pytest
import time
from unittest.mock import patch, MagicMock

from runlayer.validator import validator, get_validator_info, is_validator, create_validator
from runlayer.client import RunLayerClient
from runlayer.models.proof import RunProof


class TestValidatorDecorator:
    """Test the @validator decorator functionality."""
    
    def test_basic_validator_creation(self, test_client):
        """Test creating a basic validator."""
        @validator(name="test_validator", version="1.0.0", client=test_client)
        def test_func(x: int) -> bool:
            return x > 0
        
        # Test validator metadata
        config = get_validator_info(test_func)
        assert config is not None
        assert config.name == "test_validator"
        assert config.version == "1.0.0"
        assert config.client == test_client
        assert config.cache_results == True
        assert config.auto_sign == True
    
    def test_validator_execution(self, test_client):
        """Test validator execution creates proofs."""
        @validator(name="execution_test", version="1.0.0", client=test_client)
        def validate_positive(x: int) -> bool:
            return x > 0
        
        # Execute validator
        result = validate_positive(5)
        
        # Check result
        assert result == True
        
        # Check proof was created
        proofs = test_client.list_proofs(validator_name="execution_test")
        assert len(proofs) == 1
        
        proof = proofs[0]
        assert proof.validator_name == "execution_test"
        assert proof.validator_version == "1.0.0"
        assert proof.input_data == {"args": [5], "kwargs": {}}
        assert proof.output_data == True
        assert proof.execution_time_ms > 0
    
    def test_validator_caching(self, test_client):
        """Test validator result caching."""
        call_count = 0
        
        @validator(name="cache_test", version="1.0.0", client=test_client, cache_results=True)
        def cached_validator(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call
        result1 = cached_validator(10)
        assert result1 == 20
        assert call_count == 1
        
        # Second call with same input should use cache
        result2 = cached_validator(10)
        assert result2 == 20
        assert call_count == 1  # Function not called again
        
        # Different input should call function
        result3 = cached_validator(20)
        assert result3 == 40
        assert call_count == 2
    
    def test_validator_without_caching(self, test_client):
        """Test validator without result caching."""
        call_count = 0
        
        @validator(name="no_cache_test", version="1.0.0", client=test_client, cache_results=False)
        def no_cache_validator(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # Multiple calls with same input
        no_cache_validator(10)
        no_cache_validator(10)
        
        # Function should be called each time
        assert call_count == 2
    
    def test_validator_error_handling(self, test_client):
        """Test validator error handling."""
        @validator(name="error_test", version="1.0.0", client=test_client)
        def error_validator(x: int) -> int:
            if x < 0:
                raise ValueError("Negative numbers not allowed")
            return x * 2
        
        # Successful execution
        result = error_validator(5)
        assert result == 10
        
        # Error execution
        with pytest.raises(ValueError, match="Negative numbers not allowed"):
            error_validator(-1)
        
        # Check both proofs were created
        proofs = test_client.list_proofs(validator_name="error_test")
        assert len(proofs) == 2
        
        # Check error proof
        error_proof = next((p for p in proofs if "error" in str(p.output_data)), None)
        assert error_proof is not None
        assert error_proof.status.value == "failed"
    
    def test_validator_metadata(self, test_client):
        """Test validator metadata inclusion."""
        @validator(
            name="metadata_test", 
            version="1.0.0", 
            client=test_client,
            description="Test validator with metadata",
            metadata={"team": "test", "env": "dev"}
        )
        def metadata_validator(x: str) -> str:
            return x.upper()
        
        result = metadata_validator("hello")
        assert result == "HELLO"
        
        # Check metadata in proof
        proofs = test_client.list_proofs(validator_name="metadata_test")
        assert len(proofs) == 1
        
        proof = proofs[0]
        assert proof.metadata["team"] == "test"
        assert proof.metadata["env"] == "dev"
        assert proof.metadata["description"] == "Test validator with metadata"
        assert "correlation_id" in proof.metadata
    
    def test_validator_performance_tracking(self, test_client):
        """Test validator performance tracking."""
        @validator(name="perf_test", version="1.0.0", client=test_client)
        def slow_validator(delay_ms: int) -> str:
            time.sleep(delay_ms / 1000.0)  # Convert ms to seconds
            return "completed"
        
        result = slow_validator(100)  # 100ms delay
        assert result == "completed"
        
        # Check execution time was recorded
        proofs = test_client.list_proofs(validator_name="perf_test")
        assert len(proofs) == 1
        
        proof = proofs[0]
        assert proof.execution_time_ms >= 90  # Allow some variance
        assert proof.execution_time_ms <= 200  # But not too much
    
    def test_validator_with_kwargs(self, test_client):
        """Test validator with keyword arguments."""
        @validator(name="kwargs_test", version="1.0.0", client=test_client)
        def kwargs_validator(x: int, multiplier: int = 2, prefix: str = "result") -> str:
            return f"{prefix}: {x * multiplier}"
        
        # Test with positional args
        result1 = kwargs_validator(5)
        assert result1 == "result: 10"
        
        # Test with keyword args
        result2 = kwargs_validator(5, multiplier=3, prefix="answer")
        assert result2 == "answer: 15"
        
        # Check proofs have correct input data
        proofs = test_client.list_proofs(validator_name="kwargs_test")
        assert len(proofs) == 2
        
        # Check first proof
        proof1 = proofs[1]  # Most recent first
        assert proof1.input_data["args"] == [5]
        assert proof1.input_data["kwargs"] == {}
        
        # Check second proof
        proof2 = proofs[0]
        assert proof2.input_data["args"] == [5]
        assert proof2.input_data["kwargs"] == {"multiplier": 3, "prefix": "answer"}


class TestValidatorUtilities:
    """Test validator utility functions."""
    
    def test_get_validator_info(self, test_client):
        """Test getting validator info from decorated function."""
        @validator(name="info_test", version="2.0.0", client=test_client)
        def test_func():
            return True
        
        config = get_validator_info(test_func)
        assert config is not None
        assert config.name == "info_test"
        assert config.version == "2.0.0"
        
        # Test with non-validator function
        def regular_func():
            return True
        
        config = get_validator_info(regular_func)
        assert config is None
    
    def test_is_validator(self, test_client):
        """Test checking if function is a validator."""
        @validator(name="check_test", version="1.0.0", client=test_client)
        def validator_func():
            return True
        
        def regular_func():
            return True
        
        assert is_validator(validator_func) == True
        assert is_validator(regular_func) == False
    
    def test_create_validator_programmatically(self, test_client):
        """Test creating validator programmatically."""
        def my_function(x: int) -> bool:
            return x > 0
        
        validator_func = create_validator(
            my_function,
            name="programmatic_test",
            version="1.0.0",
            client=test_client
        )
        
        # Test it works
        result = validator_func(5)
        assert result == True
        
        # Test metadata
        config = get_validator_info(validator_func)
        assert config.name == "programmatic_test"
        assert config.version == "1.0.0"
        
        # Check proof was created
        proofs = test_client.list_proofs(validator_name="programmatic_test")
        assert len(proofs) == 1


class TestValidatorIntegration:
    """Test validator integration with client and storage."""
    
    def test_validator_with_default_client(self):
        """Test validator using default client."""
        from runlayer import get_default_client, set_default_client
        
        # Create a test client and set as default
        temp_client = RunLayerClient(workspace="default-test", auto_sync=False)
        set_default_client(temp_client)
        
        @validator(name="default_client_test", version="1.0.0")
        def test_with_default():
            return "success"
        
        result = test_with_default()
        assert result == "success"
        
        # Check proof was created in default client
        proofs = temp_client.list_proofs(validator_name="default_client_test")
        assert len(proofs) == 1
    
    def test_validator_signing(self, test_client):
        """Test validator proof signing."""
        @validator(name="signing_test", version="1.0.0", client=test_client, auto_sign=True)
        def signed_validator(data: str) -> str:
            return data.upper()
        
        result = signed_validator("hello")
        assert result == "HELLO"
        
        # Check proof was signed
        proofs = test_client.list_proofs(validator_name="signing_test")
        assert len(proofs) == 1
        
        proof = proofs[0]
        assert proof.signature is not None
        assert len(proof.signature) > 0
        
        # Verify proof integrity
        assert proof.is_valid() == True
    
    def test_validator_without_signing(self, test_client):
        """Test validator without automatic signing."""
        @validator(name="no_sign_test", version="1.0.0", client=test_client, auto_sign=False)
        def unsigned_validator(data: str) -> str:
            return data.lower()
        
        result = unsigned_validator("HELLO")
        assert result == "hello"
        
        # Check proof was not signed
        proofs = test_client.list_proofs(validator_name="no_sign_test")
        assert len(proofs) == 1
        
        proof = proofs[0]
        assert proof.signature is None
