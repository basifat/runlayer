"""
Python Validator Executor - Story 7: Basic Validator Framework

Executes Python validators with sandboxing and security controls.
"""

import ast
import asyncio
import io
import logging
import resource
import sys
import time
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from typing import Any, Dict, Optional
import traceback
import uuid

from .interface import (
    ValidatorInterface,
    ValidatorResult,
    ValidationStatus,
    ValidationError,
    ValidatorConfig,
    ValidatorType
)

logger = logging.getLogger(__name__)


class PythonValidatorExecutor(ValidatorInterface):
    """
    Executes Python validators with security and resource controls.
    
    Features:
    - Code sandboxing with restricted builtins
    - Memory and CPU limits
    - Timeout handling
    - Error capture and reporting
    - Performance monitoring
    """
    
    def __init__(
        self, 
        validator_id: str, 
        validator_code: str,
        config: Optional[ValidatorConfig] = None
    ):
        super().__init__(validator_id, config)
        self.validator_code = validator_code
        self.compiled_code = None
        self._validate_and_compile()
    
    def _get_validator_type(self) -> ValidatorType:
        """Return Python validator type."""
        return ValidatorType.PYTHON
    
    def _validate_and_compile(self) -> None:
        """Validate and compile Python code."""
        try:
            # Parse AST to validate syntax
            tree = ast.parse(self.validator_code)
            
            # Basic security checks
            self._check_security_violations(tree)
            
            # Compile code
            self.compiled_code = compile(tree, f"<validator:{self.validator_id}>", "exec")
            
        except SyntaxError as e:
            raise ValidationError(
                code="SYNTAX_ERROR",
                message=f"Python syntax error: {e}",
                details={"line": e.lineno, "offset": e.offset}
            )
        except Exception as e:
            raise ValidationError(
                code="COMPILATION_ERROR",
                message=f"Failed to compile validator: {e}"
            )
    
    def _check_security_violations(self, tree: ast.AST) -> None:
        """Check for security violations in AST."""
        
        # Forbidden imports and functions
        forbidden_imports = {
            'os', 'sys', 'subprocess', 'socket', 'urllib', 'requests',
            'multiprocessing', 'threading', 'asyncio', 'concurrent',
            'importlib', '__import__', 'eval', 'exec', 'compile'
        }
        
        forbidden_attributes = {
            '__import__', '__builtins__', '__globals__', '__locals__',
            '__dict__', '__class__', '__bases__', '__subclasses__'
        }
        
        class SecurityChecker(ast.NodeVisitor):
            def visit_Import(self, node):
                for alias in node.names:
                    if alias.name in forbidden_imports:
                        raise ValidationError(
                            code="FORBIDDEN_IMPORT",
                            message=f"Import '{alias.name}' is not allowed"
                        )
                self.generic_visit(node)
            
            def visit_ImportFrom(self, node):
                if node.module in forbidden_imports:
                    raise ValidationError(
                        code="FORBIDDEN_IMPORT",
                        message=f"Import from '{node.module}' is not allowed"
                    )
                self.generic_visit(node)
            
            def visit_Attribute(self, node):
                if isinstance(node.attr, str) and node.attr in forbidden_attributes:
                    raise ValidationError(
                        code="FORBIDDEN_ATTRIBUTE",
                        message=f"Access to '{node.attr}' is not allowed"
                    )
                self.generic_visit(node)
            
            def visit_Call(self, node):
                # Check for dangerous function calls
                if isinstance(node.func, ast.Name):
                    if node.func.id in {'eval', 'exec', 'compile', '__import__'}:
                        raise ValidationError(
                            code="FORBIDDEN_FUNCTION",
                            message=f"Function '{node.func.id}' is not allowed"
                        )
                self.generic_visit(node)
        
        checker = SecurityChecker()
        checker.visit(tree)
    
    async def validate(
        self, 
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidatorResult:
        """Execute Python validator with sandboxing."""
        
        result = ValidatorResult(
            validator_id=self.validator_id,
            status=ValidationStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        
        try:
            # Set resource limits
            self._set_resource_limits()
            
            # Execute in sandbox
            start_time = time.time()
            validation_result = await self._execute_sandboxed(input_data, context)
            end_time = time.time()
            
            # Update result
            result.execution_time_ms = int((end_time - start_time) * 1000)
            result.completed_at = datetime.utcnow()
            result.status = ValidationStatus.COMPLETED
            
            # Parse validation output
            if isinstance(validation_result, dict):
                result.is_valid = validation_result.get("is_valid")
                result.confidence_score = validation_result.get("confidence_score")
                result.output_data = validation_result.get("output_data", validation_result)
            elif isinstance(validation_result, bool):
                result.is_valid = validation_result
                result.output_data = {"result": validation_result}
            else:
                result.output_data = {"result": validation_result}
            
            logger.info(
                f"Python validator {self.validator_id} completed in {result.execution_time_ms}ms"
            )
            
        except asyncio.TimeoutError:
            result.status = ValidationStatus.TIMEOUT
            result.error = ValidationError(
                code="EXECUTION_TIMEOUT",
                message=f"Validator execution exceeded {self.config.timeout_seconds}s timeout"
            )
            result.completed_at = datetime.utcnow()
            
        except Exception as e:
            result.status = ValidationStatus.FAILED
            result.error = ValidationError(
                code="EXECUTION_ERROR",
                message=str(e),
                details={"exception_type": type(e).__name__},
                traceback=traceback.format_exc()
            )
            result.completed_at = datetime.utcnow()
            
            logger.error(f"Python validator {self.validator_id} failed: {e}", exc_info=True)
        
        return result
    
    async def _execute_sandboxed(
        self, 
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Execute validator code in sandboxed environment."""
        
        # Create restricted globals
        safe_globals = {
            '__builtins__': {
                # Safe built-ins only
                'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'tuple', 'set',
                'min', 'max', 'sum', 'abs', 'round', 'sorted', 'reversed',
                'enumerate', 'zip', 'range', 'isinstance', 'hasattr', 'getattr',
                'print'  # Allow print for debugging
            },
            # Standard library modules (safe subset)
            'json': __import__('json'),
            'math': __import__('math'),
            're': __import__('re'),
            'datetime': __import__('datetime'),
            'uuid': __import__('uuid'),
            # Input data
            'input_data': input_data,
            'context': context or {},
            # Result container
            'result': None
        }
        
        # Capture stdout/stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # Execute with timeout
                await asyncio.wait_for(
                    self._run_in_executor(safe_globals),
                    timeout=self.config.timeout_seconds
                )
            
            # Get result
            validation_result = safe_globals.get('result')
            
            # If no explicit result, try to find a validate function
            if validation_result is None and 'validate' in safe_globals:
                validate_func = safe_globals['validate']
                if callable(validate_func):
                    validation_result = validate_func(input_data)
            
            # Capture output
            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()
            
            if stderr_output:
                logger.warning(f"Validator {self.validator_id} stderr: {stderr_output}")
            
            # Return result with captured output
            if isinstance(validation_result, dict):
                validation_result['stdout'] = stdout_output
                validation_result['stderr'] = stderr_output
            else:
                validation_result = {
                    'result': validation_result,
                    'stdout': stdout_output,
                    'stderr': stderr_output
                }
            
            return validation_result
            
        except asyncio.TimeoutError:
            raise
        except Exception as e:
            # Include captured output in error
            stdout_output = stdout_capture.getvalue()
            stderr_output = stderr_capture.getvalue()
            
            error_details = {
                'stdout': stdout_output,
                'stderr': stderr_output,
                'exception_type': type(e).__name__
            }
            
            raise ValidationError(
                code="EXECUTION_ERROR",
                message=str(e),
                details=error_details,
                traceback=traceback.format_exc()
            )
    
    async def _run_in_executor(self, safe_globals: Dict[str, Any]) -> None:
        """Run compiled code in executor."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: exec(self.compiled_code, safe_globals)
        )
    
    def _set_resource_limits(self) -> None:
        """Set resource limits for execution."""
        try:
            # Memory limit (soft limit)
            memory_limit = self.config.memory_limit_mb * 1024 * 1024  # Convert to bytes
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
            
            # CPU time limit
            cpu_limit = self.config.timeout_seconds
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
            
        except (OSError, ValueError) as e:
            logger.warning(f"Failed to set resource limits: {e}")
    
    async def health_check(self) -> bool:
        """Check if validator is healthy."""
        try:
            # Simple syntax check
            if self.compiled_code is None:
                return False
            
            # Test execution with dummy data
            test_result = await self.validate(
                {"test": True},
                {"health_check": True}
            )
            
            return test_result.status in [ValidationStatus.COMPLETED, ValidationStatus.FAILED]
            
        except Exception as e:
            logger.error(f"Health check failed for validator {self.validator_id}: {e}")
            return False


class PythonValidatorFactory:
    """Factory for creating Python validators."""
    
    @staticmethod
    def create_validator(
        validator_id: str,
        validator_code: str,
        config: Optional[ValidatorConfig] = None
    ) -> PythonValidatorExecutor:
        """Create a Python validator instance."""
        return PythonValidatorExecutor(validator_id, validator_code, config)
    
    @staticmethod
    def supports_type(validator_type: ValidatorType) -> bool:
        """Check if factory supports Python validators."""
        return validator_type == ValidatorType.PYTHON
