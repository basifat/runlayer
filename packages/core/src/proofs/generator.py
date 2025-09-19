"""
Proof Generator - Story 9: Basic Proof Generation

Orchestrates proof generation with multiple formats and performance optimization.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import asyncio

from .interface import (
    ProofInterface, ProofData, ProofMetadata, ValidationResult,
    ProofFormat, ProofConfig, ProofError
)
from .json_proof import JSONProofGenerator

logger = logging.getLogger(__name__)


class ProofGenerator:
    """
    Central proof generator with multiple format support.
    
    Features:
    - Multiple proof format support
    - Performance optimization (<3 seconds)
    - Caching for repeated requests
    - Error handling and retry logic
    - Statistics tracking
    """
    
    def __init__(self, config: ProofConfig):
        self.config = config
        self.generators: Dict[ProofFormat, ProofInterface] = {}
        self.proof_cache: Dict[str, ProofData] = {}
        
        # Performance tracking
        self.stats = {
            "total_generated": 0,
            "successful_generated": 0,
            "failed_generated": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "average_generation_time_ms": 0.0
        }
        
        # Initialize generators
        self._initialize_generators()
    
    def _initialize_generators(self) -> None:
        """Initialize proof generators for supported formats."""
        try:
            # JSON generator (primary format)
            self.generators[ProofFormat.JSON] = JSONProofGenerator(self.config)
            
            logger.info("Initialized proof generators")
            
        except Exception as e:
            logger.error(f"Failed to initialize proof generators: {e}")
            raise ProofError(
                f"Generator initialization failed: {e}",
                error_code="INIT_ERROR"
            )
    
    async def generate_proof(
        self,
        validation_result: ValidationResult,
        proof_format: Optional[ProofFormat] = None,
        use_cache: bool = None,
        **kwargs
    ) -> ProofData:
        """
        Generate proof from validation results.
        
        Args:
            validation_result: Validation result to create proof from
            proof_format: Optional format override
            use_cache: Whether to use caching (defaults to config)
            **kwargs: Additional generation options
            
        Returns:
            Generated proof data
        """
        start_time = datetime.utcnow()
        
        try:
            # Use default format if not specified
            format = proof_format or self.config.default_format
            
            # Check if generator exists for format
            if format not in self.generators:
                raise ProofError(
                    f"No generator available for format: {format}",
                    error_code="UNSUPPORTED_FORMAT"
                )
            
            # Check cache if enabled
            use_cache = use_cache if use_cache is not None else self.config.enable_caching
            if use_cache:
                cached_proof = await self._get_cached_proof(validation_result, format)
                if cached_proof:
                    self.stats["cache_hits"] += 1
                    logger.debug(f"Retrieved cached proof for execution {validation_result.execution_id}")
                    return cached_proof
                else:
                    self.stats["cache_misses"] += 1
            
            # Generate new proof
            generator = self.generators[format]
            proof_data = await generator.generate_proof(validation_result, format, **kwargs)
            
            # Cache if enabled
            if use_cache:
                await self._cache_proof(proof_data)
            
            # Update statistics
            generation_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._update_stats(generation_time, True)
            
            logger.info(
                f"Generated proof {proof_data.proof_id} in {generation_time:.2f}ms "
                f"(format: {format.value})"
            )
            
            return proof_data
            
        except Exception as e:
            generation_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._update_stats(generation_time, False)
            
            logger.error(f"Failed to generate proof: {e}")
            
            if isinstance(e, ProofError):
                raise
            else:
                raise ProofError(
                    f"Proof generation failed: {e}",
                    error_code="GENERATION_ERROR",
                    details={"error": str(e), "generation_time_ms": generation_time}
                )
    
    async def validate_proof(
        self,
        proof_data: ProofData,
        strict: bool = True
    ) -> bool:
        """
        Validate a proof using appropriate generator.
        
        Args:
            proof_data: Proof to validate
            strict: Whether to perform strict validation
            
        Returns:
            True if proof is valid, False otherwise
        """
        try:
            format = proof_data.metadata.proof_format
            
            if format not in self.generators:
                logger.error(f"No generator available for format: {format}")
                return False
            
            generator = self.generators[format]
            is_valid = await generator.validate_proof(proof_data)
            
            if strict and not is_valid:
                logger.error(f"Strict validation failed for proof {proof_data.proof_id}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Proof validation error: {e}")
            return False
    
    async def serialize_proof(
        self,
        proof_data: ProofData,
        format: Optional[ProofFormat] = None
    ) -> bytes:
        """Serialize proof using appropriate generator."""
        try:
            format = format or proof_data.metadata.proof_format
            
            if format not in self.generators:
                raise ProofError(
                    f"No generator available for format: {format}",
                    error_code="UNSUPPORTED_FORMAT"
                )
            
            generator = self.generators[format]
            return await generator.serialize_proof(proof_data, format)
            
        except Exception as e:
            if isinstance(e, ProofError):
                raise
            else:
                raise ProofError(
                    f"Proof serialization failed: {e}",
                    error_code="SERIALIZATION_ERROR"
                )
    
    async def deserialize_proof(
        self,
        proof_bytes: bytes,
        format: ProofFormat
    ) -> ProofData:
        """Deserialize proof using appropriate generator."""
        try:
            if format not in self.generators:
                raise ProofError(
                    f"No generator available for format: {format}",
                    error_code="UNSUPPORTED_FORMAT"
                )
            
            generator = self.generators[format]
            return await generator.deserialize_proof(proof_bytes, format)
            
        except Exception as e:
            if isinstance(e, ProofError):
                raise
            else:
                raise ProofError(
                    f"Proof deserialization failed: {e}",
                    error_code="DESERIALIZATION_ERROR"
                )
    
    async def _get_cached_proof(
        self,
        validation_result: ValidationResult,
        format: ProofFormat
    ) -> Optional[ProofData]:
        """Get cached proof if available."""
        try:
            # Create cache key from validation result
            cache_key = self._generate_cache_key(validation_result, format)
            
            cached_proof = self.proof_cache.get(cache_key)
            if cached_proof:
                # Check if cache entry is still valid
                if cached_proof.metadata.expires_at:
                    if datetime.utcnow() > cached_proof.metadata.expires_at:
                        # Remove expired entry
                        del self.proof_cache[cache_key]
                        return None
                
                return cached_proof
            
            return None
            
        except Exception as e:
            logger.error(f"Cache retrieval error: {e}")
            return None
    
    async def _cache_proof(self, proof_data: ProofData) -> None:
        """Cache proof data."""
        try:
            # Create cache key
            cache_key = self._generate_cache_key(
                proof_data.validation_result,
                proof_data.metadata.proof_format
            )
            
            # Store in cache
            self.proof_cache[cache_key] = proof_data
            
            # Cleanup old entries if cache is getting large
            if len(self.proof_cache) > 1000:  # Simple cleanup threshold
                await self._cleanup_cache()
            
        except Exception as e:
            logger.error(f"Cache storage error: {e}")
    
    def _generate_cache_key(
        self,
        validation_result: ValidationResult,
        format: ProofFormat
    ) -> str:
        """Generate cache key for validation result."""
        return f"{validation_result.execution_id}:{format.value}"
    
    async def _cleanup_cache(self) -> None:
        """Clean up expired cache entries."""
        try:
            current_time = datetime.utcnow()
            expired_keys = []
            
            for key, proof_data in self.proof_cache.items():
                if proof_data.metadata.expires_at:
                    if current_time > proof_data.metadata.expires_at:
                        expired_keys.append(key)
            
            for key in expired_keys:
                del self.proof_cache[key]
            
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
            
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
    
    def _update_stats(self, generation_time_ms: float, success: bool) -> None:
        """Update generation statistics."""
        self.stats["total_generated"] += 1
        
        if success:
            self.stats["successful_generated"] += 1
        else:
            self.stats["failed_generated"] += 1
        
        # Update average generation time
        total_successful = self.stats["successful_generated"]
        if total_successful > 0:
            current_avg = self.stats["average_generation_time_ms"]
            self.stats["average_generation_time_ms"] = (
                (current_avg * (total_successful - 1) + generation_time_ms) / total_successful
            )
    
    def get_supported_formats(self) -> List[ProofFormat]:
        """Get all supported proof formats."""
        return list(self.generators.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get generation statistics."""
        return {
            **self.stats,
            "cache_size": len(self.proof_cache),
            "supported_formats": [f.value for f in self.get_supported_formats()]
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Get proof generator configuration."""
        return self.config.to_dict()
    
    async def health_check(self) -> bool:
        """Check proof generator health."""
        try:
            # Check if generators are available
            if not self.generators:
                return False
            
            # Test basic functionality with minimal validation result
            test_result = ValidationResult(
                validator_id="health-check",
                execution_id="health-check",
                workspace_id="health-check",
                user_id="health-check",
                input_data={"test": True},
                output_data={"valid": True},
                is_valid=True
            )
            
            # Try to generate a proof
            proof_data = await self.generate_proof(test_result, use_cache=False)
            
            # Try to validate it
            is_valid = await self.validate_proof(proof_data)
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# Global proof generator instance
proof_generator = ProofGenerator(ProofConfig())
