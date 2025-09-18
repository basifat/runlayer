#!/usr/bin/env python3
"""
RunLayer SDK - Integration Example

This file demonstrates how to integrate RunLayer SDK into existing applications:
- FastAPI integration
- Data pipeline validation
- ML model validation
- CI/CD integration patterns
- Production deployment considerations

Run this example:
    python examples/integration_example.py
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any
from runlayer import validator, RunLayerClient
import json
import tempfile
from pathlib import Path


# Example 1: FastAPI Integration
def fastapi_integration_example():
    """Demonstrate FastAPI integration with RunLayer validators."""
    print("🌐 FastAPI Integration Example")
    print("-" * 35)
    
    # This would be in your FastAPI app
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
        
        app = FastAPI(title="RunLayer + FastAPI Demo")
        
        # Configure RunLayer client for the API
        client = RunLayerClient(
            workspace="fastapi-demo",
            auto_sync=False  # Configure based on your needs
        )
        
        # Pydantic models for API
        class UserData(BaseModel):
            name: str
            email: str
            age: int
            preferences: Dict[str, Any] = {}
        
        class ValidationResponse(BaseModel):
            is_valid: bool
            errors: List[str] = []
            validation_id: str
            timestamp: str
        
        # RunLayer validators for API endpoints
        @validator(name="api_user_validation", version="1.0.0", client=client)
        def validate_api_user(user_data: dict) -> dict:
            """Validate user data from API requests."""
            errors = []
            
            # Name validation
            if not user_data.get("name") or len(user_data["name"]) < 2:
                errors.append("Name must be at least 2 characters long")
            
            # Email validation
            email = user_data.get("email", "")
            if not email or "@" not in email:
                errors.append("Valid email address is required")
            
            # Age validation
            age = user_data.get("age")
            if not isinstance(age, int) or age < 0 or age > 150:
                errors.append("Age must be a valid number between 0 and 150")
            
            return {
                "is_valid": len(errors) == 0,
                "errors": errors,
                "validated_fields": list(user_data.keys()),
                "validation_timestamp": datetime.utcnow().isoformat()
            }
        
        # API endpoint using RunLayer validation
        @app.post("/users/validate", response_model=ValidationResponse)
        async def validate_user_endpoint(user: UserData):
            """Validate user data with RunLayer proof generation."""
            
            # Convert Pydantic model to dict for validation
            user_dict = user.dict()
            
            # Validate using RunLayer (creates proof automatically)
            validation_result = validate_api_user(user_dict)
            
            # Get the proof ID for tracking
            recent_proofs = client.list_proofs(validator_name="api_user_validation", limit=1)
            proof_id = recent_proofs[0].id if recent_proofs else "unknown"
            
            return ValidationResponse(
                is_valid=validation_result["is_valid"],
                errors=validation_result["errors"],
                validation_id=proof_id,
                timestamp=validation_result["validation_timestamp"]
            )
        
        print("✅ FastAPI app configured with RunLayer validation")
        print("   - POST /users/validate endpoint created")
        print("   - Automatic proof generation for all validations")
        print("   - Validation results include proof IDs for tracking")
        
        # Simulate API usage
        test_users = [
            {"name": "John Doe", "email": "john@example.com", "age": 30},
            {"name": "X", "email": "invalid-email", "age": -5}  # Invalid data
        ]
        
        for i, user_data in enumerate(test_users, 1):
            print(f"\n🧪 Testing user {i}: {user_data}")
            result = validate_api_user(user_data)
            print(f"   Result: {'✅ Valid' if result['is_valid'] else '❌ Invalid'}")
            if result['errors']:
                print(f"   Errors: {', '.join(result['errors'])}")
        
    except ImportError:
        print("⚠️ FastAPI not installed. Install with: pip install fastapi uvicorn")
        print("   This example shows how to integrate RunLayer with FastAPI")


# Example 2: Data Pipeline Integration
def data_pipeline_example():
    """Demonstrate data pipeline integration."""
    print("\n🔄 Data Pipeline Integration Example")
    print("-" * 40)
    
    # Configure client for data pipeline
    client = RunLayerClient(
        workspace="data-pipeline",
        auto_sync=False
    )
    
    @validator(name="data_quality_check", version="2.0.0", client=client)
    def validate_data_batch(batch_data: List[dict]) -> dict:
        """Validate a batch of data in pipeline."""
        total_records = len(batch_data)
        valid_records = 0
        errors = []
        
        for i, record in enumerate(batch_data):
            record_errors = []
            
            # Check required fields
            required_fields = ["id", "timestamp", "value"]
            for field in required_fields:
                if field not in record:
                    record_errors.append(f"Missing field: {field}")
            
            # Validate data types and ranges
            if "value" in record:
                try:
                    value = float(record["value"])
                    if value < 0:
                        record_errors.append("Value must be non-negative")
                except (ValueError, TypeError):
                    record_errors.append("Value must be numeric")
            
            if not record_errors:
                valid_records += 1
            else:
                errors.append(f"Record {i}: {', '.join(record_errors)}")
        
        quality_score = valid_records / total_records if total_records > 0 else 0
        
        return {
            "total_records": total_records,
            "valid_records": valid_records,
            "invalid_records": total_records - valid_records,
            "quality_score": round(quality_score, 3),
            "errors": errors[:10],  # Limit error list
            "batch_timestamp": datetime.utcnow().isoformat(),
            "quality_grade": (
                "A" if quality_score >= 0.95 else
                "B" if quality_score >= 0.85 else
                "C" if quality_score >= 0.70 else
                "F"
            )
        }
    
    # Simulate data pipeline batches
    print("📊 Processing data pipeline batches...")
    
    # Good batch
    good_batch = [
        {"id": 1, "timestamp": "2024-01-01T10:00:00Z", "value": 100.5},
        {"id": 2, "timestamp": "2024-01-01T10:01:00Z", "value": 95.2},
        {"id": 3, "timestamp": "2024-01-01T10:02:00Z", "value": 102.1}
    ]
    
    result = validate_data_batch(good_batch)
    print(f"✅ Good batch: {result['quality_score']} quality score (Grade {result['quality_grade']})")
    
    # Bad batch
    bad_batch = [
        {"id": 1, "value": 100.5},  # Missing timestamp
        {"id": 2, "timestamp": "2024-01-01T10:01:00Z", "value": -50},  # Negative value
        {"timestamp": "2024-01-01T10:02:00Z", "value": "invalid"}  # Missing ID, invalid value
    ]
    
    result = validate_data_batch(bad_batch)
    print(f"❌ Bad batch: {result['quality_score']} quality score (Grade {result['quality_grade']})")
    print(f"   Errors: {len(result['errors'])} validation issues found")


# Example 3: ML Model Validation
def ml_model_validation_example():
    """Demonstrate ML model validation integration."""
    print("\n🤖 ML Model Validation Example")
    print("-" * 35)
    
    client = RunLayerClient(
        workspace="ml-validation",
        auto_sync=False
    )
    
    @validator(name="model_prediction_validation", version="1.0.0", client=client)
    def validate_model_predictions(predictions: List[float], ground_truth: List[float] = None) -> dict:
        """Validate ML model predictions."""
        import math
        
        result = {
            "prediction_count": len(predictions),
            "valid_predictions": 0,
            "invalid_predictions": 0,
            "prediction_range": {},
            "quality_metrics": {}
        }
        
        # Basic prediction validation
        valid_preds = []
        for pred in predictions:
            if isinstance(pred, (int, float)) and not math.isnan(pred) and not math.isinf(pred):
                valid_preds.append(pred)
                result["valid_predictions"] += 1
            else:
                result["invalid_predictions"] += 1
        
        if valid_preds:
            result["prediction_range"] = {
                "min": min(valid_preds),
                "max": max(valid_preds),
                "mean": sum(valid_preds) / len(valid_preds)
            }
        
        # If ground truth is provided, calculate metrics
        if ground_truth and len(ground_truth) == len(valid_preds):
            mse = sum((p - t) ** 2 for p, t in zip(valid_preds, ground_truth)) / len(valid_preds)
            mae = sum(abs(p - t) for p, t in zip(valid_preds, ground_truth)) / len(valid_preds)
            
            result["quality_metrics"] = {
                "mse": round(mse, 4),
                "mae": round(mae, 4),
                "rmse": round(math.sqrt(mse), 4)
            }
        
        result["validation_passed"] = (
            result["valid_predictions"] == result["prediction_count"] and
            result["prediction_count"] > 0
        )
        
        return result
    
    # Simulate model predictions
    print("🔮 Validating ML model predictions...")
    
    # Good predictions
    good_predictions = [0.85, 0.92, 0.78, 0.88, 0.91]
    ground_truth = [0.87, 0.90, 0.80, 0.85, 0.93]
    
    result = validate_model_predictions(good_predictions, ground_truth)
    print(f"✅ Model validation passed: {result['validation_passed']}")
    print(f"   Valid predictions: {result['valid_predictions']}/{result['prediction_count']}")
    if result["quality_metrics"]:
        print(f"   RMSE: {result['quality_metrics']['rmse']}")
        print(f"   MAE: {result['quality_metrics']['mae']}")
    
    # Bad predictions (with NaN and inf values)
    bad_predictions = [0.85, float('nan'), float('inf'), 0.78, "invalid"]
    
    result = validate_model_predictions(bad_predictions)
    print(f"❌ Model validation failed: {result['validation_passed']}")
    print(f"   Valid predictions: {result['valid_predictions']}/{result['prediction_count']}")
    print(f"   Invalid predictions: {result['invalid_predictions']}")


# Example 4: CI/CD Integration Pattern
def cicd_integration_example():
    """Demonstrate CI/CD integration patterns."""
    print("\n🔄 CI/CD Integration Example")
    print("-" * 32)
    
    client = RunLayerClient(
        workspace="cicd-validation",
        auto_sync=False  # In CI/CD, you might want to sync manually
    )
    
    @validator(name="deployment_readiness_check", version="1.0.0", client=client)
    def validate_deployment_readiness(deployment_config: dict) -> dict:
        """Validate deployment configuration for CI/CD pipeline."""
        checks = {
            "config_complete": True,
            "security_compliant": True,
            "performance_acceptable": True,
            "dependencies_resolved": True
        }
        
        issues = []
        
        # Check required configuration
        required_configs = ["app_name", "environment", "version", "resources"]
        for config in required_configs:
            if config not in deployment_config:
                checks["config_complete"] = False
                issues.append(f"Missing required config: {config}")
        
        # Security checks
        if deployment_config.get("environment") == "production":
            if not deployment_config.get("ssl_enabled", False):
                checks["security_compliant"] = False
                issues.append("SSL must be enabled for production")
            
            if deployment_config.get("debug_mode", False):
                checks["security_compliant"] = False
                issues.append("Debug mode must be disabled for production")
        
        # Performance checks
        resources = deployment_config.get("resources", {})
        if resources.get("memory_mb", 0) < 512:
            checks["performance_acceptable"] = False
            issues.append("Minimum 512MB memory required")
        
        if resources.get("cpu_cores", 0) < 1:
            checks["performance_acceptable"] = False
            issues.append("Minimum 1 CPU core required")
        
        # Dependency checks (simplified)
        dependencies = deployment_config.get("dependencies", [])
        if len(dependencies) == 0:
            checks["dependencies_resolved"] = False
            issues.append("No dependencies specified")
        
        all_checks_passed = all(checks.values())
        
        return {
            "deployment_ready": all_checks_passed,
            "checks": checks,
            "issues": issues,
            "environment": deployment_config.get("environment", "unknown"),
            "validation_timestamp": datetime.utcnow().isoformat(),
            "recommendation": (
                "✅ Deployment approved" if all_checks_passed else
                "❌ Deployment blocked - resolve issues first"
            )
        }
    
    # Simulate CI/CD deployment validation
    print("🚀 Validating deployment configurations...")
    
    # Good deployment config
    good_config = {
        "app_name": "my-api",
        "environment": "production",
        "version": "1.2.3",
        "resources": {
            "memory_mb": 1024,
            "cpu_cores": 2
        },
        "ssl_enabled": True,
        "debug_mode": False,
        "dependencies": ["fastapi", "uvicorn", "runlayer"]
    }
    
    result = validate_deployment_readiness(good_config)
    print(f"✅ Production config: {result['recommendation']}")
    
    # Bad deployment config
    bad_config = {
        "app_name": "my-api",
        "environment": "production",
        # Missing version and resources
        "ssl_enabled": False,  # Security issue
        "debug_mode": True,    # Security issue
        "dependencies": []     # No dependencies
    }
    
    result = validate_deployment_readiness(bad_config)
    print(f"❌ Bad config: {result['recommendation']}")
    print(f"   Issues found: {len(result['issues'])}")
    for issue in result['issues'][:3]:  # Show first 3 issues
        print(f"   - {issue}")


async def cloud_sync_example():
    """Demonstrate cloud synchronization (mock)."""
    print("\n☁️ Cloud Synchronization Example")
    print("-" * 35)
    
    client = RunLayerClient(
        workspace="cloud-sync-demo",
        auto_sync=False,
        api_key="demo-key-12345"  # Mock API key
    )
    
    # Create some validations
    @validator(name="sync_test_validator", version="1.0.0", client=client)
    def test_validation(data: str) -> dict:
        return {"processed": True, "length": len(data)}
    
    # Generate some proofs
    test_validation("test data 1")
    test_validation("test data 2")
    test_validation("test data 3")
    
    # Check sync status
    stats = client.get_workspace_stats()
    print(f"📊 Workspace stats:")
    print(f"   Total proofs: {stats['total_proofs']}")
    print(f"   Synced proofs: {stats['synced_proofs']}")
    print(f"   Pending sync: {stats['total_proofs'] - stats['synced_proofs']}")
    
    # Test connection (will fail in demo, but shows the pattern)
    print(f"\n🔗 Testing cloud connection...")
    try:
        is_connected = await client.test_connection()
        print(f"   Connection status: {'✅ Connected' if is_connected else '❌ Not connected'}")
    except Exception as e:
        print(f"   Connection test: ⚠️ {str(e)[:50]}...")
    
    print(f"   💡 In production, configure RUNLAYER_API_KEY environment variable")
    print(f"   💡 Enable auto_sync=True for automatic cloud synchronization")


def production_considerations():
    """Show production deployment considerations."""
    print("\n🏭 Production Deployment Considerations")
    print("-" * 45)
    
    print("📋 Configuration checklist:")
    print("   ✅ Set RUNLAYER_API_KEY environment variable")
    print("   ✅ Configure appropriate workspace names")
    print("   ✅ Set storage quotas based on expected usage")
    print("   ✅ Enable auto_sync for cloud backup")
    print("   ✅ Configure appropriate logging levels")
    print("   ✅ Set up monitoring for proof generation rates")
    print("   ✅ Plan for storage cleanup of old proofs")
    
    print("\n🔧 Example production configuration:")
    production_config = {
        "workspace": "production-app-v1",
        "api_key": "${RUNLAYER_API_KEY}",
        "auto_sync": True,
        "max_storage_mb": 1000,
        "sync_interval_seconds": 300,
        "encrypt_local_storage": True,
        "batch_sync_size": 100
    }
    
    print(json.dumps(production_config, indent=2))
    
    print("\n📊 Monitoring recommendations:")
    print("   - Track proof generation rate")
    print("   - Monitor storage usage")
    print("   - Alert on sync failures")
    print("   - Track validation performance")
    print("   - Monitor error rates by validator")


async def main():
    """Run all integration examples."""
    print("🚀 RunLayer SDK - Integration Examples")
    print("=" * 45)
    
    # Run all examples
    fastapi_integration_example()
    data_pipeline_example()
    ml_model_validation_example()
    cicd_integration_example()
    await cloud_sync_example()
    production_considerations()
    
    print("\n✨ Integration examples completed!")
    print("\n💡 Key integration patterns demonstrated:")
    print("- FastAPI web service integration with automatic proof generation")
    print("- Data pipeline quality validation with batch processing")
    print("- ML model prediction validation with quality metrics")
    print("- CI/CD deployment readiness checks with approval gates")
    print("- Cloud synchronization patterns for distributed systems")
    print("- Production deployment configuration and monitoring")
    
    print("\n🔗 Next steps:")
    print("- Integrate @validator decorators into your existing functions")
    print("- Configure workspace and API keys for your environment")
    print("- Set up monitoring and alerting for validation metrics")
    print("- Implement proof verification in your audit processes")


if __name__ == "__main__":
    asyncio.run(main())
