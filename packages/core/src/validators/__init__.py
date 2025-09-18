"""
Validator Execution Framework - Story 7: Basic Validator Framework

12-Factor App Compliance:
- III. Config: All validator configuration from environment
- IV. Backing Services: Redis job queue integration
- VI. Processes: Stateless validator execution

DRY Principles Applied:
- Single ValidatorExecutor for all execution patterns
- Reusable validation interfaces
- Centralized error handling and timeout management
- No code duplication across validator types
"""

from .interface import ValidatorInterface, ValidatorResult, ValidationError
from .executor import ValidatorExecutor, ExecutionContext
from .registry import ValidatorRegistry, validator_registry
from .python_executor import PythonValidatorExecutor

__all__ = [
    "ValidatorInterface",
    "ValidatorResult", 
    "ValidationError",
    "ValidatorExecutor",
    "ExecutionContext",
    "ValidatorRegistry",
    "validator_registry",
    "PythonValidatorExecutor"
]
