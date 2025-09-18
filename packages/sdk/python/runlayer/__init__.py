r"""
RunLayer Python SDK - Temporal for AI Validation

The RunLayer SDK provides a seamless way to add validation to any Python function
using the @validator decorator. It creates local proofs that sync to the cloud
for sharing and verification.

Basic Usage:
    from runlayer import validator
    
    @validator(name="email_validation", version="1.0.0")
    def validate_email(email: str) -> bool:
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    # Usage automatically creates and stores proofs
    result = validate_email("test@example.com")

Advanced Usage:
    from runlayer import RunLayerClient, validator
    
    client = RunLayerClient(
        api_key="your-api-key",
        workspace="my-project",
        auto_sync=True
    )
    
    @validator(name="data_validation", version="2.1.0", client=client)
    def validate_data(data: dict) -> bool:
        return all(key in data for key in ["id", "name", "email"])
"""

__version__ = "0.1.0"
__author__ = "RunLayer Team"
__email__ = "sdk@runlayer.com"

# Core imports for public API
from .validator import validator
from .client import RunLayerClient
from .models.proof import RunProof, ProofStatus
from .models.workspace import Workspace, WorkspaceConfig

# Storage imports
from .storage.local import LocalProofLake
from .storage.sync import CloudSync

# Utility imports
from .utils.logging import get_logger

# Public API
__all__ = [
    # Core functionality
    "validator",
    "RunLayerClient",
    
    # Models
    "RunProof",
    "ProofStatus", 
    "Workspace",
    "WorkspaceConfig",
    
    # Storage
    "LocalProofLake",
    "CloudSync",
    
    # Utilities
    "get_logger",
    
    # Metadata
    "__version__",
]

# Default client instance for simple usage
_default_client = None

def get_default_client() -> RunLayerClient:
    """Get or create the default RunLayer client."""
    global _default_client
    if _default_client is None:
        _default_client = RunLayerClient()
    return _default_client

def set_default_client(client: RunLayerClient) -> None:
    """Set the default RunLayer client."""
    global _default_client
    _default_client = client

# Configure default logging
import logging
logging.getLogger("runlayer").setLevel(logging.INFO)
