"""
Tests for utility modules - logging and crypto.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import shutil

from runlayer.utils.logging import (
    get_logger, setup_logging, set_correlation_id, get_correlation_id,
    PerformanceLogger
)
from runlayer.utils.crypto import (
    KeyManager, generate_keypair, sign_data, verify_signature,
    load_private_key_from_pem, load_public_key_from_pem
)


class TestLogging:
    """Test logging utilities."""
    
    def test_get_logger(self):
        """Test getting a logger."""
        logger = get_logger("test_module")
        
        assert logger is not None
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')
        assert hasattr(logger, 'debug')
        assert hasattr(logger, 'warning')
    
    def test_setup_logging(self):
        """Test logging setup."""
        # Test with different configurations
        setup_logging(level="DEBUG", json_format=False, include_timestamp=True)
        logger = get_logger("test_setup")
        
        # Should not raise any errors
        logger.info("Test message")
        logger.debug("Debug message")
        logger.error("Error message")
    
    def test_correlation_id(self):
        """Test correlation ID management."""
        # Set correlation ID
        corr_id = set_correlation_id("test-123")
        assert corr_id == "test-123"
        assert get_correlation_id() == "test-123"
        
        # Auto-generate correlation ID
        auto_id = set_correlation_id()
        assert auto_id is not None
        assert len(auto_id) == 8
        assert get_correlation_id() == auto_id
        
        # Clear correlation ID for other tests
        set_correlation_id(None)
    
    def test_performance_logger(self):
        """Test performance logging context manager."""
        logger = get_logger("test_perf")
        
        with PerformanceLogger(logger, "test_operation") as perf:
            # Simulate some work
            import time
            time.sleep(0.01)  # 10ms
        
        # Should complete without errors
        assert perf is not None
    
    def test_performance_logger_with_exception(self):
        """Test performance logger with exception."""
        logger = get_logger("test_perf_error")
        
        with pytest.raises(ValueError):
            with PerformanceLogger(logger, "failing_operation"):
                raise ValueError("Test error")


class TestCrypto:
    """Test cryptographic utilities."""
    
    @pytest.fixture
    def temp_workspace_dir(self):
        """Create temporary workspace directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_generate_keypair(self):
        """Test Ed25519 key pair generation."""
        private_pem, public_pem = generate_keypair()
        
        assert isinstance(private_pem, str)
        assert isinstance(public_pem, str)
        assert len(private_pem) > 0
        assert len(public_pem) > 0
        
        # Should be valid base64
        import base64
        private_bytes = base64.b64decode(private_pem)
        public_bytes = base64.b64decode(public_pem)
        
        assert len(private_bytes) > 0
        assert len(public_bytes) > 0
    
    def test_sign_and_verify_data(self):
        """Test data signing and verification."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        
        # Generate key pair
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Test data
        test_data = "Hello, RunLayer!"
        
        # Sign data
        signature = sign_data(test_data, private_key)
        assert isinstance(signature, str)
        assert len(signature) > 0
        
        # Verify signature
        is_valid = verify_signature(test_data, signature, public_key)
        assert is_valid == True
        
        # Verify with wrong data
        is_invalid = verify_signature("Wrong data", signature, public_key)
        assert is_invalid == False
    
    def test_load_keys_from_pem(self):
        """Test loading keys from PEM strings."""
        # Generate key pair
        private_pem, public_pem = generate_keypair()
        
        # Load keys
        private_key = load_private_key_from_pem(private_pem)
        public_key = load_public_key_from_pem(public_pem)
        
        # Test they work together
        test_data = "Test signing"
        signature = sign_data(test_data, private_key)
        is_valid = verify_signature(test_data, signature, public_key)
        
        assert is_valid == True
    
    def test_key_manager_initialization(self, temp_workspace_dir):
        """Test KeyManager initialization."""
        key_manager = KeyManager(temp_workspace_dir)
        
        assert key_manager.workspace_path == temp_workspace_dir
        assert key_manager.private_key_path == temp_workspace_dir / "private_key.pem"
        assert key_manager.public_key_path == temp_workspace_dir / "public_key.pem"
    
    def test_key_manager_key_generation(self, temp_workspace_dir):
        """Test KeyManager key generation."""
        key_manager = KeyManager(temp_workspace_dir)
        
        # Initially no keys
        assert not key_manager.private_key_path.exists()
        assert not key_manager.public_key_path.exists()
        
        # Ensure keys exist (should generate them)
        key_manager.ensure_keys_exist()
        
        # Keys should now exist
        assert key_manager.private_key_path.exists()
        assert key_manager.public_key_path.exists()
        
        # Check file permissions on private key (Unix-like systems)
        import stat
        mode = key_manager.private_key_path.stat().st_mode
        permissions = stat.filemode(mode)
        # Should be readable/writable by owner only
        assert permissions.startswith('-rw-------') or permissions.startswith('-rw-r--r--')
    
    def test_key_manager_get_keys(self, temp_workspace_dir):
        """Test KeyManager key retrieval."""
        key_manager = KeyManager(temp_workspace_dir)
        
        # Get private key (should generate if not exists)
        private_key = key_manager.get_private_key()
        assert private_key is not None
        
        # Get public key
        public_key = key_manager.get_public_key()
        assert public_key is not None
        
        # Test they work together
        test_data = "KeyManager test"
        signature = sign_data(test_data, private_key)
        is_valid = verify_signature(test_data, signature, public_key)
        
        assert is_valid == True
    
    def test_key_manager_get_public_key_bytes(self, temp_workspace_dir):
        """Test KeyManager public key bytes."""
        key_manager = KeyManager(temp_workspace_dir)
        
        public_key_bytes = key_manager.get_public_key_bytes()
        
        assert isinstance(public_key_bytes, bytes)
        assert len(public_key_bytes) == 32  # Ed25519 public key is 32 bytes
    
    def test_key_manager_persistence(self, temp_workspace_dir):
        """Test KeyManager key persistence."""
        # Create first key manager and generate keys
        key_manager1 = KeyManager(temp_workspace_dir)
        private_key1 = key_manager1.get_private_key()
        public_key1 = key_manager1.get_public_key()
        
        # Create second key manager (should load existing keys)
        key_manager2 = KeyManager(temp_workspace_dir)
        private_key2 = key_manager2.get_private_key()
        public_key2 = key_manager2.get_public_key()
        
        # Keys should be the same
        from cryptography.hazmat.primitives import serialization
        
        private_bytes1 = private_key1.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        private_bytes2 = private_key2.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        assert private_bytes1 == private_bytes2
    
    def test_signature_verification_edge_cases(self):
        """Test signature verification edge cases."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Test with empty data
        signature = sign_data("", private_key)
        assert verify_signature("", signature, public_key) == True
        
        # Test with invalid signature format
        assert verify_signature("test", "invalid-signature", public_key) == False
        
        # Test with different public key
        other_private_key = Ed25519PrivateKey.generate()
        other_public_key = other_private_key.public_key()
        
        test_data = "test data"
        signature = sign_data(test_data, private_key)
        
        # Should fail with wrong public key
        assert verify_signature(test_data, signature, other_public_key) == False


class TestUtilsIntegration:
    """Test integration between utility modules."""
    
    def test_logging_with_crypto_operations(self, temp_dir):
        """Test logging during crypto operations."""
        logger = get_logger("crypto_test")
        
        # Set correlation ID
        corr_id = set_correlation_id("crypto-test-123")
        
        with PerformanceLogger(logger, "key_generation"):
            key_manager = KeyManager(temp_dir)
            private_key = key_manager.get_private_key()
            
            # Sign some data
            test_data = f"Test data with correlation ID: {corr_id}"
            signature = sign_data(test_data, private_key)
            
            assert signature is not None
            assert len(signature) > 0
    
    def test_json_logging_format(self):
        """Test JSON logging format."""
        from runlayer.utils.logging import setup_logging
        
        # Configure with JSON format
        setup_logging(json_format=True)
        
        # Get a logger and test it works
        logger = get_logger("json_test")
        logger.info("Test JSON logging")
        
        # Should not raise any errors
        assert True
    
    def test_error_handling_in_crypto(self):
        """Test error handling in crypto operations."""
        logger = get_logger("crypto_error_test")
        
        # Test signing with invalid key type
        with pytest.raises(Exception):
            sign_data("test", "not-a-key")
        
        # Test verification with invalid signature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        # Should return False, not raise exception
        result = verify_signature("test", "invalid", public_key)
        assert result == False
