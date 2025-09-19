"""
Proof Generation System - Story 9: Basic Proof Generation

12-Factor App Compliance:
- III. Config: All proof configuration from environment
- IV. Backing Services: Storage and database as attached resources
- VI. Processes: Stateless proof generation

DRY Principles Applied:
- Single ProofInterface for all proof types
- Reusable proof generation patterns
- Centralized cryptographic operations
- No code duplication across proof formats
"""

from .interface import (
    ProofInterface,
    ProofData,
    ProofMetadata,
    ProofFormat,
    ProofStatus,
    ProofError,
    ValidationResult,
    ProofConfig
)
from .generator import ProofGenerator, proof_generator
from .json_proof import JSONProofGenerator
from .storage import ProofStorage, proof_storage
from .manager import ProofManager, proof_manager

__all__ = [
    "ProofInterface",
    "ProofData",
    "ProofMetadata", 
    "ProofFormat",
    "ProofStatus",
    "ProofError",
    "ValidationResult",
    "ProofConfig",
    "ProofGenerator",
    "proof_generator",
    "JSONProofGenerator",
    "ProofStorage",
    "proof_storage",
    "ProofManager",
    "proof_manager"
]
