"""
Proof Interface Definition - Story 9: Basic Proof Generation

Defines the core interfaces for proof generation following senior engineer patterns.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import uuid
import hashlib
import json


class ProofFormat(str, Enum):
    """Supported proof formats."""
    JSON = "json"
    JWT = "jwt"
    XML = "xml"
    BINARY = "binary"


class ProofStatus(str, Enum):
    """Proof generation status."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALID = "invalid"


@dataclass
class ValidationResult:
    """Validation result data for proof generation."""
    
    # Execution information
    validator_id: str
    execution_id: str
    workspace_id: str
    user_id: str
    
    # Input/output data
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    
    # Validation outcome
    is_valid: bool
    confidence_score: Optional[float] = None
    error_message: Optional[str] = None
    
    # Timing information
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime = field(default_factory=datetime.utcnow)
    execution_time_ms: float = 0.0
    
    # Artifacts
    input_artifacts: List[str] = field(default_factory=list)  # Artifact IDs
    output_artifacts: List[str] = field(default_factory=list)  # Artifact IDs
    
    # Additional metadata
    validator_version: Optional[str] = None
    platform_version: Optional[str] = None
    custom_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "validator_id": self.validator_id,
            "execution_id": self.execution_id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "is_valid": self.is_valid,
            "confidence_score": self.confidence_score,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "input_artifacts": self.input_artifacts,
            "output_artifacts": self.output_artifacts,
            "validator_version": self.validator_version,
            "platform_version": self.platform_version,
            "custom_metadata": self.custom_metadata
        }


@dataclass
class ProofMetadata:
    """Metadata for generated proofs."""
    
    # Identification
    proof_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    proof_version: str = "1.0"
    proof_format: ProofFormat = ProofFormat.JSON
    
    # Timestamps
    generated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    # Source information
    validator_id: str = ""
    execution_id: str = ""
    workspace_id: str = ""
    user_id: str = ""
    
    # Proof characteristics
    content_hash: str = ""  # SHA-256 of proof content
    signature: Optional[str] = None  # Cryptographic signature
    signature_algorithm: str = "Ed25519"
    
    # Size and performance
    size_bytes: int = 0
    generation_time_ms: float = 0.0
    
    # Storage information
    storage_path: Optional[str] = None
    is_immutable: bool = True
    
    # Additional metadata
    tags: Dict[str, str] = field(default_factory=dict)
    custom_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "proof_id": self.proof_id,
            "proof_version": self.proof_version,
            "proof_format": self.proof_format.value,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "validator_id": self.validator_id,
            "execution_id": self.execution_id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "content_hash": self.content_hash,
            "signature": self.signature,
            "signature_algorithm": self.signature_algorithm,
            "size_bytes": self.size_bytes,
            "generation_time_ms": self.generation_time_ms,
            "storage_path": self.storage_path,
            "is_immutable": self.is_immutable,
            "tags": self.tags,
            "custom_metadata": self.custom_metadata
        }


@dataclass
class ProofData:
    """Complete proof data structure."""
    
    metadata: ProofMetadata
    validation_result: ValidationResult
    proof_content: Dict[str, Any]
    
    @property
    def proof_id(self) -> str:
        """Get proof ID."""
        return self.metadata.proof_id
    
    @property
    def is_valid(self) -> bool:
        """Check if validation was successful."""
        return self.validation_result.is_valid
    
    @property
    def content_hash(self) -> str:
        """Get content hash."""
        return self.metadata.content_hash
    
    def calculate_content_hash(self) -> str:
        """Calculate SHA-256 hash of proof content."""
        content_str = json.dumps(self.proof_content, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()
    
    def update_content_hash(self) -> None:
        """Update metadata hash from content."""
        self.metadata.content_hash = self.calculate_content_hash()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metadata": self.metadata.to_dict(),
            "validation_result": self.validation_result.to_dict(),
            "proof_content": self.proof_content
        }


@dataclass
class ProofConfig:
    """Configuration for proof generation."""
    
    # Format settings
    default_format: ProofFormat = ProofFormat.JSON
    enable_compression: bool = True
    max_size_bytes: int = 10 * 1024 * 1024  # 10MB
    
    # Cryptographic settings
    enable_signing: bool = True
    signing_algorithm: str = "Ed25519"
    signing_key: Optional[str] = None
    
    # Performance settings
    max_generation_time_seconds: int = 3
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    
    # Storage settings
    enable_immutable_storage: bool = True
    default_expiry_days: Optional[int] = None
    
    # Validation settings
    validate_on_generation: bool = True
    require_artifacts: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "default_format": self.default_format.value,
            "enable_compression": self.enable_compression,
            "max_size_bytes": self.max_size_bytes,
            "enable_signing": self.enable_signing,
            "signing_algorithm": self.signing_algorithm,
            "signing_key": "***" if self.signing_key else None,
            "max_generation_time_seconds": self.max_generation_time_seconds,
            "enable_caching": self.enable_caching,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "enable_immutable_storage": self.enable_immutable_storage,
            "default_expiry_days": self.default_expiry_days,
            "validate_on_generation": self.validate_on_generation,
            "require_artifacts": self.require_artifacts
        }


class ProofError(Exception):
    """Base exception for proof operations."""
    
    def __init__(self, message: str, error_code: str = "PROOF_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class ProofInterface(ABC):
    """Abstract interface for proof generators."""
    
    def __init__(self, config: ProofConfig):
        self.config = config
    
    @abstractmethod
    async def generate_proof(
        self,
        validation_result: ValidationResult,
        proof_format: Optional[ProofFormat] = None,
        **kwargs
    ) -> ProofData:
        """
        Generate a proof from validation results.
        
        Args:
            validation_result: The validation result to create proof from
            proof_format: Optional format override
            **kwargs: Additional generation options
            
        Returns:
            Generated proof data
            
        Raises:
            ProofError: If proof generation fails
        """
        pass
    
    @abstractmethod
    async def validate_proof(self, proof_data: ProofData) -> bool:
        """
        Validate a generated proof.
        
        Args:
            proof_data: The proof to validate
            
        Returns:
            True if proof is valid, False otherwise
        """
        pass
    
    @abstractmethod
    async def serialize_proof(
        self,
        proof_data: ProofData,
        format: Optional[ProofFormat] = None
    ) -> bytes:
        """
        Serialize proof to bytes for storage.
        
        Args:
            proof_data: The proof to serialize
            format: Optional format override
            
        Returns:
            Serialized proof bytes
        """
        pass
    
    @abstractmethod
    async def deserialize_proof(
        self,
        proof_bytes: bytes,
        format: Optional[ProofFormat] = None
    ) -> ProofData:
        """
        Deserialize proof from bytes.
        
        Args:
            proof_bytes: Serialized proof data
            format: Optional format hint
            
        Returns:
            Deserialized proof data
        """
        pass
    
    def get_supported_formats(self) -> List[ProofFormat]:
        """Get list of supported proof formats."""
        return [ProofFormat.JSON]
    
    def get_config(self) -> Dict[str, Any]:
        """Get proof generator configuration."""
        return self.config.to_dict()
