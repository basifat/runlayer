"""
Validator Registry - Story 7: Basic Validator Framework

Manages validator registration, discovery, and lifecycle.
"""

import logging
from typing import Dict, List, Optional, Type
import uuid

from .interface import ValidatorInterface, ValidatorConfig, ValidatorType, ValidatorFactory
from .python_executor import PythonValidatorFactory

logger = logging.getLogger(__name__)


class ValidatorRegistry:
    """
    Central registry for validator management.
    
    Features:
    - Validator registration and discovery
    - Factory pattern for different validator types
    - Lifecycle management
    - Health monitoring
    """
    
    def __init__(self):
        self.validators: Dict[str, ValidatorInterface] = {}
        self.factories: Dict[ValidatorType, ValidatorFactory] = {}
        self.validator_metadata: Dict[str, Dict] = {}
        
        # Register built-in factories
        self._register_builtin_factories()
    
    def _register_builtin_factories(self) -> None:
        """Register built-in validator factories."""
        python_factory = PythonValidatorFactory()
        self.factories[ValidatorType.PYTHON] = python_factory
    
    def register_factory(
        self, 
        validator_type: ValidatorType, 
        factory: ValidatorFactory
    ) -> None:
        """Register a validator factory."""
        self.factories[validator_type] = factory
        logger.info(f"Registered factory for validator type: {validator_type.value}")
    
    def create_validator(
        self,
        validator_type: ValidatorType,
        validator_code: str,
        validator_id: Optional[str] = None,
        config: Optional[ValidatorConfig] = None
    ) -> str:
        """
        Create and register a new validator.
        
        Args:
            validator_type: Type of validator to create
            validator_code: Validator code/configuration
            validator_id: Optional validator ID (auto-generated if not provided)
            config: Optional validator configuration
            
        Returns:
            Validator ID
        """
        if validator_type not in self.factories:
            raise ValueError(f"No factory registered for validator type: {validator_type.value}")
        
        # Generate ID if not provided
        if validator_id is None:
            validator_id = f"{validator_type.value}_{uuid.uuid4().hex[:8]}"
        
        # Check for duplicate ID
        if validator_id in self.validators:
            raise ValueError(f"Validator with ID '{validator_id}' already exists")
        
        # Create validator
        factory = self.factories[validator_type]
        validator = factory.create_validator(validator_id, validator_code, config)
        
        # Register validator
        self.validators[validator_id] = validator
        self.validator_metadata[validator_id] = {
            "validator_type": validator_type.value,
            "created_at": validator.get_metadata().get("created_at"),
            "config": config.to_dict() if config else ValidatorConfig().to_dict(),
            "code_hash": self._hash_code(validator_code)
        }
        
        logger.info(f"Created and registered validator: {validator_id}")
        return validator_id
    
    def get_validator(self, validator_id: str) -> Optional[ValidatorInterface]:
        """Get validator by ID."""
        return self.validators.get(validator_id)
    
    def list_validators(
        self, 
        validator_type: Optional[ValidatorType] = None
    ) -> List[Dict]:
        """
        List registered validators.
        
        Args:
            validator_type: Optional filter by validator type
            
        Returns:
            List of validator metadata
        """
        validators = []
        
        for validator_id, validator in self.validators.items():
            metadata = self.validator_metadata.get(validator_id, {})
            
            # Filter by type if specified
            if validator_type and metadata.get("validator_type") != validator_type.value:
                continue
            
            validators.append({
                "validator_id": validator_id,
                "validator_type": metadata.get("validator_type"),
                "created_at": metadata.get("created_at"),
                "config": metadata.get("config"),
                "healthy": True  # TODO: Implement health check
            })
        
        return validators
    
    def remove_validator(self, validator_id: str) -> bool:
        """Remove validator from registry."""
        if validator_id in self.validators:
            del self.validators[validator_id]
            self.validator_metadata.pop(validator_id, None)
            logger.info(f"Removed validator: {validator_id}")
            return True
        return False
    
    async def health_check_all(self) -> Dict[str, bool]:
        """Run health checks on all validators."""
        health_status = {}
        
        for validator_id, validator in self.validators.items():
            try:
                is_healthy = await validator.health_check()
                health_status[validator_id] = is_healthy
                
                if not is_healthy:
                    logger.warning(f"Validator {validator_id} failed health check")
                    
            except Exception as e:
                logger.error(f"Health check error for validator {validator_id}: {e}")
                health_status[validator_id] = False
        
        return health_status
    
    def get_stats(self) -> Dict:
        """Get registry statistics."""
        stats = {
            "total_validators": len(self.validators),
            "validators_by_type": {},
            "registered_factories": list(self.factories.keys())
        }
        
        # Count by type
        for metadata in self.validator_metadata.values():
            validator_type = metadata.get("validator_type", "unknown")
            stats["validators_by_type"][validator_type] = (
                stats["validators_by_type"].get(validator_type, 0) + 1
            )
        
        return stats
    
    def _hash_code(self, code: str) -> str:
        """Generate hash of validator code."""
        import hashlib
        return hashlib.sha256(code.encode()).hexdigest()[:16]


# Global registry instance
validator_registry = ValidatorRegistry()
