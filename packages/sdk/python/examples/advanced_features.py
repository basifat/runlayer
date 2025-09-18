#!/usr/bin/env python3
"""
RunLayer SDK - Advanced Features Examples

This file demonstrates advanced features of the RunLayer SDK:
- Custom client configuration
- Multiple workspaces
- Metadata and versioning
- Performance monitoring
- Error handling and recovery
- Proof verification

Run this example:
    python examples/advanced_features.py
"""

import asyncio
from datetime import datetime
from pathlib import Path
from runlayer import validator, RunLayerClient
import tempfile
import json


async def main():
    """Demonstrate advanced RunLayer SDK features."""
    print("🚀 RunLayer SDK - Advanced Features")
    print("=" * 45)
    
    # Create temporary directory for this example
    temp_dir = Path(tempfile.mkdtemp())
    print(f"📁 Using temporary directory: {temp_dir}")
    
    # Example 1: Custom Client Configuration
    print("\n⚙️ Example 1: Custom Client Configuration")
    print("-" * 45)
    
    # Create client with custom configuration
    client = RunLayerClient(
        workspace="advanced-demo",
        storage_path=temp_dir,
        auto_sync=False,  # Disable for demo
        max_storage_mb=50,
        encrypt_local_storage=False,  # Disable for demo simplicity
        batch_sync_size=10
    )
    
    print(f"✅ Created workspace: {client.workspace.config.name}")
    print(f"📍 Storage path: {client.workspace.config.storage_path}")
    print(f"💾 Max storage: {client.workspace.config.max_storage_mb}MB")
    
    # Example 2: Validators with Rich Metadata
    print("\n📝 Example 2: Rich Metadata and Versioning")
    print("-" * 45)
    
    @validator(
        name="ai_content_validator",
        version="2.1.0",
        client=client,
        description="Validates AI-generated content for quality and safety",
        metadata={
            "team": "ai-safety",
            "category": "content-moderation",
            "compliance": ["GDPR", "CCPA"],
            "model_version": "gpt-4-turbo",
            "environment": "production"
        }
    )
    def validate_ai_content(content: str, safety_threshold: float = 0.8) -> dict:
        """
        Validate AI-generated content for quality and safety.
        
        Args:
            content: The content to validate
            safety_threshold: Minimum safety score (0.0 to 1.0)
            
        Returns:
            Validation result with scores and recommendations
        """
        # Simulate AI content analysis
        import hashlib
        content_hash = hashlib.md5(content.encode()).hexdigest()
        
        # Mock scoring based on content characteristics
        word_count = len(content.split())
        char_count = len(content)
        
        # Simulate various quality metrics
        quality_score = min(1.0, word_count / 100)  # Better with more words
        safety_score = 1.0 - (len([c for c in content if not c.isalnum() and c != ' ']) / char_count)
        coherence_score = min(1.0, char_count / word_count / 10) if word_count > 0 else 0
        
        overall_score = (quality_score + safety_score + coherence_score) / 3
        
        return {
            "is_valid": overall_score >= safety_threshold,
            "overall_score": round(overall_score, 3),
            "metrics": {
                "quality_score": round(quality_score, 3),
                "safety_score": round(safety_score, 3),
                "coherence_score": round(coherence_score, 3)
            },
            "content_stats": {
                "word_count": word_count,
                "char_count": char_count,
                "content_hash": content_hash
            },
            "recommendations": [
                "Content meets quality standards" if overall_score >= safety_threshold
                else "Content needs improvement",
                f"Safety score: {safety_score:.1%}",
                f"Consider review" if overall_score < 0.7 else "Approved for publication"
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # Test AI content validation
    test_contents = [
        "This is a high-quality article about machine learning applications in healthcare.",
        "Short text.",
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        "!@#$%^&*()_+ Special characters everywhere !@#$%^&*()"
    ]
    
    for i, content in enumerate(test_contents, 1):
        print(f"\n📄 Content {i}: {content[:50]}{'...' if len(content) > 50 else ''}")
        result = validate_ai_content(content, safety_threshold=0.6)
        print(f"   ✅ Valid: {result['is_valid']}")
        print(f"   📊 Overall Score: {result['overall_score']}")
        print(f"   💡 Recommendation: {result['recommendations'][0]}")
    
    # Example 3: Performance Monitoring
    print("\n⏱️ Example 3: Performance Monitoring")
    print("-" * 40)
    
    @validator(name="performance_validator", version="1.0.0", client=client)
    def expensive_computation(n: int) -> dict:
        """Simulate expensive computation for performance testing."""
        import time
        import math
        
        start_time = time.perf_counter()
        
        # Simulate expensive computation
        result = 0
        for i in range(n * 1000):
            result += math.sqrt(i + 1)
        
        computation_time = time.perf_counter() - start_time
        
        return {
            "input_size": n,
            "result": round(result, 2),
            "computation_time_seconds": round(computation_time, 4),
            "operations_performed": n * 1000,
            "performance_category": (
                "fast" if computation_time < 0.01 else
                "medium" if computation_time < 0.1 else
                "slow"
            )
        }
    
    # Test performance with different input sizes
    test_sizes = [1, 5, 10, 20]
    performance_results = []
    
    for size in test_sizes:
        print(f"🔄 Testing with input size: {size}")
        result = expensive_computation(size)
        performance_results.append(result)
        print(f"   ⏱️ Computation time: {result['computation_time_seconds']}s")
        print(f"   🏷️ Category: {result['performance_category']}")
    
    # Example 4: Error Handling and Recovery
    print("\n🚨 Example 4: Error Handling and Recovery")
    print("-" * 45)
    
    @validator(name="robust_validator", version="1.0.0", client=client)
    def robust_data_processor(data, operation: str = "sum") -> dict:
        """
        Robust data processor with comprehensive error handling.
        
        Args:
            data: Input data (should be iterable of numbers)
            operation: Operation to perform ("sum", "avg", "max", "min")
            
        Returns:
            Processing result with error handling
        """
        try:
            # Validate input data
            if not hasattr(data, '__iter__'):
                raise ValueError("Input data must be iterable")
            
            # Convert to list of numbers
            numbers = []
            for item in data:
                try:
                    numbers.append(float(item))
                except (ValueError, TypeError):
                    raise ValueError(f"Invalid number in data: {item}")
            
            if not numbers:
                raise ValueError("No valid numbers found in input data")
            
            # Perform operation
            if operation == "sum":
                result = sum(numbers)
            elif operation == "avg":
                result = sum(numbers) / len(numbers)
            elif operation == "max":
                result = max(numbers)
            elif operation == "min":
                result = min(numbers)
            else:
                raise ValueError(f"Unknown operation: {operation}")
            
            return {
                "success": True,
                "result": result,
                "operation": operation,
                "input_count": len(numbers),
                "input_data": numbers
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "operation": operation,
                "input_data": str(data)[:100]  # Truncate for safety
            }
    
    # Test with various inputs (good and bad)
    test_cases = [
        ([1, 2, 3, 4, 5], "sum"),
        ([10, 20, 30], "avg"),
        (["1", "2", "3"], "max"),  # String numbers
        ([1, 2, "invalid", 4], "sum"),  # Mixed valid/invalid
        ([], "sum"),  # Empty data
        ([1, 2, 3], "unknown_op"),  # Invalid operation
        ("not_iterable", "sum")  # Invalid input type
    ]
    
    for i, (data, operation) in enumerate(test_cases, 1):
        print(f"\n🧪 Test case {i}: {str(data)[:30]}{'...' if len(str(data)) > 30 else ''}, operation='{operation}'")
        result = robust_data_processor(data, operation)
        
        if result["success"]:
            print(f"   ✅ Success: {result['result']}")
        else:
            print(f"   ❌ Error ({result['error_type']}): {result['error']}")
    
    # Example 5: Proof Verification and Analysis
    print("\n🔍 Example 5: Proof Verification and Analysis")
    print("-" * 45)
    
    # Get all proofs from this session
    all_proofs = client.list_proofs()
    print(f"📊 Total proofs created in this session: {len(all_proofs)}")
    
    # Analyze proofs by validator
    validator_stats = {}
    for proof in all_proofs:
        validator_name = proof.validator_name
        if validator_name not in validator_stats:
            validator_stats[validator_name] = {
                "count": 0,
                "total_execution_time": 0,
                "success_count": 0,
                "error_count": 0
            }
        
        stats = validator_stats[validator_name]
        stats["count"] += 1
        stats["total_execution_time"] += proof.execution_time_ms
        
        if proof.status.value == "failed":
            stats["error_count"] += 1
        else:
            stats["success_count"] += 1
    
    print("\n📈 Validator Performance Summary:")
    for validator_name, stats in validator_stats.items():
        avg_time = stats["total_execution_time"] / stats["count"]
        success_rate = stats["success_count"] / stats["count"] * 100
        
        print(f"\n🔧 {validator_name}:")
        print(f"   📊 Executions: {stats['count']}")
        print(f"   ⏱️ Avg execution time: {avg_time:.1f}ms")
        print(f"   ✅ Success rate: {success_rate:.1f}%")
        print(f"   ❌ Errors: {stats['error_count']}")
    
    # Verify proof integrity
    print(f"\n🔐 Proof Integrity Verification:")
    valid_proofs = 0
    signed_proofs = 0
    
    for proof in all_proofs:
        if proof.is_valid():
            valid_proofs += 1
        if proof.signature:
            signed_proofs += 1
    
    print(f"   ✅ Valid proofs: {valid_proofs}/{len(all_proofs)} ({valid_proofs/len(all_proofs)*100:.1f}%)")
    print(f"   🔏 Signed proofs: {signed_proofs}/{len(all_proofs)} ({signed_proofs/len(all_proofs)*100:.1f}%)")
    
    # Example 6: Workspace Management
    print("\n🏢 Example 6: Multiple Workspace Management")
    print("-" * 45)
    
    # Create a second workspace for comparison
    client2 = RunLayerClient(
        workspace="comparison-workspace",
        storage_path=temp_dir,
        auto_sync=False
    )
    
    @validator(name="simple_validator", version="1.0.0", client=client2)
    def simple_validation(x: int) -> bool:
        return x > 0
    
    # Add some data to second workspace
    simple_validation(10)
    simple_validation(-5)
    
    # Compare workspaces
    stats1 = client.get_workspace_stats()
    stats2 = client2.get_workspace_stats()
    
    print(f"📊 Workspace Comparison:")
    print(f"   Workspace 1 ({stats1['workspace_name']}): {stats1['total_proofs']} proofs")
    print(f"   Workspace 2 ({stats2['workspace_name']}): {stats2['total_proofs']} proofs")
    print(f"   Total storage: {stats1.get('storage_size_mb', 0) + stats2.get('storage_size_mb', 0):.2f}MB")
    
    print("\n✨ Advanced features demonstration completed!")
    print("\n💡 Key advanced features demonstrated:")
    print("- Custom client configuration with workspace isolation")
    print("- Rich metadata and versioning for compliance tracking")
    print("- Performance monitoring and execution time tracking")
    print("- Comprehensive error handling and recovery")
    print("- Proof integrity verification and cryptographic signatures")
    print("- Multi-workspace management and comparison")
    print("- Detailed analytics and performance profiling")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)
    print(f"\n🧹 Cleaned up temporary directory: {temp_dir}")


if __name__ == "__main__":
    asyncio.run(main())
