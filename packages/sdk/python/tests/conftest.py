"""
Pytest configuration and fixtures for RunLayer SDK tests.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import asyncio

from runlayer.client import RunLayerClient
from runlayer.models.workspace import Workspace, WorkspaceConfig
from runlayer.storage.local import LocalProofLake


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def test_workspace_config(temp_dir, request):
    """Create a test workspace configuration."""
    # Use test node ID to create unique workspace name for test isolation
    test_name = request.node.name.replace("[", "_").replace("]", "_").replace("::", "_")
    return WorkspaceConfig(
        name=f"test-workspace-{test_name}",
        storage_path=temp_dir,
        api_key="test-api-key",
        auto_sync=False,  # Disable auto sync in tests
        max_storage_mb=10,
        encrypt_local_storage=False  # Disable encryption for simpler tests
    )


@pytest.fixture
def test_workspace(test_workspace_config):
    """Create a test workspace."""
    workspace = Workspace(
        id="test-workspace-id",
        config=test_workspace_config
    )
    workspace.save_to_path()
    return workspace


@pytest.fixture
def test_client(test_workspace):
    """Create a test RunLayer client."""
    return RunLayerClient(
        workspace=test_workspace.config.name,
        storage_path=test_workspace.config.storage_path,
        api_key=test_workspace.config.api_key,
        auto_sync=False
    )


@pytest.fixture
def local_storage(test_workspace):
    """Create a test local storage instance."""
    db_path = test_workspace.get_database_path()
    return LocalProofLake(db_path, encrypt=False)


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx client for testing cloud sync."""
    mock_client = AsyncMock()
    
    # Mock successful authentication
    mock_auth_response = AsyncMock()
    mock_auth_response.status_code = 200
    mock_auth_response.json.return_value = {
        "access_token": "test-access-token",
        "refresh_token": "test-refresh-token",
        "expires_in": 900
    }
    mock_client.post.return_value = mock_auth_response
    
    # Mock successful health check
    mock_health_response = AsyncMock()
    mock_health_response.status_code = 200
    mock_client.get.return_value = mock_health_response
    
    return mock_client


@pytest.fixture
def sample_proof_data():
    """Sample data for creating test proofs."""
    return {
        "validator_name": "test_validator",
        "validator_version": "1.0.0",
        "input_data": {"email": "test@example.com"},
        "output_data": True,
        "execution_time_ms": 50,
        "workspace_id": "test-workspace-id"
    }


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_key_manager():
    """Create a mock key manager for testing crypto operations."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    
    mock_manager = MagicMock()
    
    # Generate real keys for testing
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    mock_manager.get_private_key.return_value = private_key
    mock_manager.get_public_key.return_value = public_key
    mock_manager.ensure_keys_exist.return_value = None
    
    return mock_manager


# Test data constants
TEST_EMAIL_VALID = "test@example.com"
TEST_EMAIL_INVALID = "invalid-email"
TEST_VALIDATOR_NAME = "test_email_validator"
TEST_VALIDATOR_VERSION = "1.0.0"
