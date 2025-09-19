"""
JSON Proof Generator - Story 9: Basic Proof Generation

Implements JSON-based proof generation with cryptographic signatures.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
import asyncio
import gzip

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

from .interface import (
    ProofInterface, ProofData, ProofMetadata, ValidationResult,
    ProofFormat, ProofConfig, ProofError
)

logger = logging.getLogger(__name__)


class JSONProofGenerator(ProofInterface):
    """
    JSON-based proof generator with Ed25519 signatures.
    
    Features:
    - JSON proof format with structured data
    - Ed25519 cryptographic signatures
    - Content compression for size optimization
    - Fast generation (<3 seconds)
    - Immutable proof structure
    """
    
    def __init__(self, config: ProofConfig):
        super().__init__(config)
        
        if config.enable_signing and not CRYPTOGRAPHY_AVAILABLE:
            raise ProofError(
                "Cryptography library required for proof signing",
                error_code="DEPENDENCY_MISSING"
            )
        
        self.private_key = None
        self.public_key = None
        
        if config.enable_signing:
            self._initialize_keys()
    
    def _initialize_keys(self) -> None:
        """Initialize Ed25519 keys for signing."""
        try:
            if self.config.signing_key:
                # Load existing private key
                key_bytes = bytes.fromhex(self.config.signing_key)
                self.private_key = Ed25519PrivateKey.from_private_bytes(key_bytes)
            else:
                # Generate new key pair
                self.private_key = Ed25519PrivateKey.generate()
            
            self.public_key = self.private_key.public_key()
            
            logger.info("Initialized Ed25519 keys for proof signing")
            
        except Exception as e:
            raise ProofError(
                f"Failed to initialize signing keys: {e}",
                error_code="KEY_INIT_ERROR",
                details={"error": str(e)}
            )
    
    async def generate_proof(
        self,
        validation_result: ValidationResult,
        proof_format: Optional[ProofFormat] = None,
        **kwargs
    ) -> ProofData:
        """Generate JSON proof from validation results."""
        
        start_time = datetime.utcnow()
        
        try:
            # Use default format if not specified
            format = proof_format or self.config.default_format
            
            if format != ProofFormat.JSON:
                raise ProofError(
                    f"Unsupported proof format: {format}",
                    error_code="UNSUPPORTED_FORMAT"
                )
            
            # Create proof metadata
            metadata = ProofMetadata(
                proof_format=format,
                validator_id=validation_result.validator_id,
                execution_id=validation_result.execution_id,
                workspace_id=validation_result.workspace_id,
                user_id=validation_result.user_id,
                signature_algorithm=self.config.signing_algorithm,
                is_immutable=self.config.enable_immutable_storage
            )
            
            # Set expiry if configured
            if self.config.default_expiry_days:
                metadata.expires_at = datetime.utcnow() + timedelta(
                    days=self.config.default_expiry_days
                )
            
            # Generate proof content
            proof_content = await self._generate_json_content(validation_result, **kwargs)
            
            # Create proof data
            proof_data = ProofData(
                metadata=metadata,
                validation_result=validation_result,
                proof_content=proof_content
            )
            
            # Update content hash
            proof_data.update_content_hash()
            
            # Sign proof if enabled
            if self.config.enable_signing:
                await self._sign_proof(proof_data)
            
            # Calculate generation time
            generation_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            metadata.generation_time_ms = generation_time
            
            # Validate generation time requirement
            if generation_time > self.config.max_generation_time_seconds * 1000:
                logger.warning(
                    f"Proof generation took {generation_time:.2f}ms, "
                    f"exceeding {self.config.max_generation_time_seconds * 1000}ms limit"
                )
            
            # Calculate size
            serialized = await self.serialize_proof(proof_data)
            metadata.size_bytes = len(serialized)
            
            # Validate size requirement
            if metadata.size_bytes > self.config.max_size_bytes:
                raise ProofError(
                    f"Proof size {metadata.size_bytes} bytes exceeds limit of {self.config.max_size_bytes} bytes",
                    error_code="PROOF_TOO_LARGE"
                )
            
            logger.info(
                f"Generated JSON proof {metadata.proof_id} in {generation_time:.2f}ms "
                f"({metadata.size_bytes} bytes)"
            )
            
            return proof_data
            
        except Exception as e:
            generation_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"Failed to generate proof after {generation_time:.2f}ms: {e}")
            
            if isinstance(e, ProofError):
                raise
            else:
                raise ProofError(
                    f"Proof generation failed: {e}",
                    error_code="GENERATION_ERROR",
                    details={"error": str(e), "generation_time_ms": generation_time}
                )
    
    async def _generate_json_content(
        self,
        validation_result: ValidationResult,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate JSON proof content structure."""
        
        # Core proof structure following RunLayer standards
        proof_content = {
            "version": "1.0",
            "type": "validation_proof",
            "specification": "https://runlayer.com/proof-spec/v1",
            
            # Validation information
            "validation": {
                "validator_id": validation_result.validator_id,
                "validator_version": validation_result.validator_version,
                "execution_id": validation_result.execution_id,
                "is_valid": validation_result.is_valid,
                "confidence_score": validation_result.confidence_score,
                "error_message": validation_result.error_message
            },
            
            # Timing information
            "execution": {
                "started_at": validation_result.started_at.isoformat() if validation_result.started_at else None,
                "completed_at": validation_result.completed_at.isoformat() if validation_result.completed_at else None,
                "execution_time_ms": validation_result.execution_time_ms,
                "platform_version": validation_result.platform_version
            },
            
            # Input/output data (potentially large)
            "data": {
                "input": validation_result.input_data,
                "output": validation_result.output_data
            },
            
            # Artifact references
            "artifacts": {
                "input_artifacts": validation_result.input_artifacts,
                "output_artifacts": validation_result.output_artifacts
            },
            
            # Context information
            "context": {
                "workspace_id": validation_result.workspace_id,
                "user_id": validation_result.user_id,
                "custom_metadata": validation_result.custom_metadata
            }
        }
        
        # Add any additional kwargs
        if kwargs:
            proof_content["additional"] = kwargs
        
        return proof_content
    
    async def _sign_proof(self, proof_data: ProofData) -> None:
        """Sign proof content with Ed25519 private key."""
        
        if not self.private_key:
            raise ProofError(
                "Private key not available for signing",
                error_code="SIGNING_KEY_MISSING"
            )
        
        try:
            # Create signing payload (metadata + content hash)
            signing_payload = {
                "proof_id": proof_data.metadata.proof_id,
                "content_hash": proof_data.metadata.content_hash,
                "generated_at": proof_data.metadata.generated_at.isoformat(),
                "validator_id": proof_data.metadata.validator_id,
                "execution_id": proof_data.metadata.execution_id
            }
            
            # Convert to canonical JSON for signing
            payload_bytes = json.dumps(
                signing_payload, 
                sort_keys=True, 
                separators=(',', ':')
            ).encode('utf-8')
            
            # Sign with Ed25519
            signature_bytes = self.private_key.sign(payload_bytes)
            proof_data.metadata.signature = signature_bytes.hex()
            
            logger.debug(f"Signed proof {proof_data.metadata.proof_id}")
            
        except Exception as e:
            raise ProofError(
                f"Failed to sign proof: {e}",
                error_code="SIGNING_ERROR",
                details={"error": str(e)}
            )
    
    async def validate_proof(self, proof_data: ProofData) -> bool:
        """Validate JSON proof structure and signature."""
        
        try:
            # Validate basic structure
            if not isinstance(proof_data.proof_content, dict):
                logger.error("Proof content is not a dictionary")
                return False
            
            # Validate required fields
            required_fields = ["version", "type", "validation", "execution", "data"]
            for field in required_fields:
                if field not in proof_data.proof_content:
                    logger.error(f"Missing required field: {field}")
                    return False
            
            # Validate content hash
            calculated_hash = proof_data.calculate_content_hash()
            if calculated_hash != proof_data.metadata.content_hash:
                logger.error("Content hash mismatch")
                return False
            
            # Validate signature if present
            if proof_data.metadata.signature and self.config.enable_signing:
                if not await self._verify_signature(proof_data):
                    logger.error("Signature verification failed")
                    return False
            
            # Validate expiry
            if proof_data.metadata.expires_at:
                if datetime.utcnow() > proof_data.metadata.expires_at:
                    logger.error("Proof has expired")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Proof validation error: {e}")
            return False
    
    async def _verify_signature(self, proof_data: ProofData) -> bool:
        """Verify Ed25519 signature."""
        
        if not self.public_key or not proof_data.metadata.signature:
            return False
        
        try:
            # Recreate signing payload
            signing_payload = {
                "proof_id": proof_data.metadata.proof_id,
                "content_hash": proof_data.metadata.content_hash,
                "generated_at": proof_data.metadata.generated_at.isoformat(),
                "validator_id": proof_data.metadata.validator_id,
                "execution_id": proof_data.metadata.execution_id
            }
            
            payload_bytes = json.dumps(
                signing_payload,
                sort_keys=True,
                separators=(',', ':')
            ).encode('utf-8')
            
            # Verify signature
            signature_bytes = bytes.fromhex(proof_data.metadata.signature)
            self.public_key.verify(signature_bytes, payload_bytes)
            
            return True
            
        except (InvalidSignature, ValueError) as e:
            logger.error(f"Signature verification failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    async def serialize_proof(
        self,
        proof_data: ProofData,
        format: Optional[ProofFormat] = None
    ) -> bytes:
        """Serialize JSON proof to bytes."""
        
        try:
            # Convert to dictionary
            proof_dict = proof_data.to_dict()
            
            # Serialize to JSON
            json_str = json.dumps(proof_dict, indent=2, sort_keys=True)
            json_bytes = json_str.encode('utf-8')
            
            # Compress if enabled
            if self.config.enable_compression:
                json_bytes = gzip.compress(json_bytes)
            
            return json_bytes
            
        except Exception as e:
            raise ProofError(
                f"Failed to serialize proof: {e}",
                error_code="SERIALIZATION_ERROR",
                details={"error": str(e)}
            )
    
    async def deserialize_proof(
        self,
        proof_bytes: bytes,
        format: Optional[ProofFormat] = None
    ) -> ProofData:
        """Deserialize JSON proof from bytes."""
        
        try:
            # Decompress if needed
            try:
                decompressed_bytes = gzip.decompress(proof_bytes)
                json_str = decompressed_bytes.decode('utf-8')
            except gzip.BadGzipFile:
                # Not compressed
                json_str = proof_bytes.decode('utf-8')
            
            # Parse JSON
            proof_dict = json.loads(json_str)
            
            # Reconstruct objects
            metadata_dict = proof_dict["metadata"]
            validation_dict = proof_dict["validation_result"]
            
            # Convert datetime strings back to datetime objects
            metadata_dict["generated_at"] = datetime.fromisoformat(metadata_dict["generated_at"])
            if metadata_dict.get("expires_at"):
                metadata_dict["expires_at"] = datetime.fromisoformat(metadata_dict["expires_at"])
            
            validation_dict["started_at"] = datetime.fromisoformat(validation_dict["started_at"])
            validation_dict["completed_at"] = datetime.fromisoformat(validation_dict["completed_at"])
            
            # Create objects
            metadata = ProofMetadata(**{k: v for k, v in metadata_dict.items() if k != "proof_format"})
            metadata.proof_format = ProofFormat(metadata_dict["proof_format"])
            
            validation_result = ValidationResult(**validation_dict)
            
            proof_data = ProofData(
                metadata=metadata,
                validation_result=validation_result,
                proof_content=proof_dict["proof_content"]
            )
            
            return proof_data
            
        except Exception as e:
            raise ProofError(
                f"Failed to deserialize proof: {e}",
                error_code="DESERIALIZATION_ERROR",
                details={"error": str(e)}
            )
    
    def get_supported_formats(self) -> List[ProofFormat]:
        """Get supported proof formats."""
        return [ProofFormat.JSON]
