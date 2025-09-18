#!/usr/bin/env python3
"""
RunLayer SDK - Basic Usage Examples

This file demonstrates the core functionality of the RunLayer SDK:
- Simple @validator decorator usage
- Automatic proof generation and storage
- Local ProofLake with offline capabilities
- Basic error handling

Run this example:
    python examples/basic_usage.py
"""

from runlayer import validator, RunLayerClient
import re


def main():
    """Demonstrate basic RunLayer SDK usage."""
    print("🚀 RunLayer SDK - Basic Usage Examples")
    print("=" * 50)
    
    # Example 1: Simple Email Validation
    print("\n📧 Example 1: Email Validation")
    print("-" * 30)
    
    @validator(name="email_validation", version="1.0.0")
    def validate_email(email: str) -> bool:
        """Validate email format using regex."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    # Test valid emails
    valid_emails = ["test@example.com", "user.name@domain.co.uk", "admin@company.org"]
    for email in valid_emails:
        result = validate_email(email)
        print(f"✅ {email}: {result}")
    
    # Test invalid emails
    invalid_emails = ["invalid-email", "missing@", "@missing.com", "no-dot@domain"]
    for email in invalid_emails:
        result = validate_email(email)
        print(f"❌ {email}: {result}")
    
    # Example 2: Data Quality Validation
    print("\n📊 Example 2: Data Quality Validation")
    print("-" * 40)
    
    @validator(name="data_quality_check", version="1.2.0")
    def validate_user_data(user_data: dict) -> dict:
        """Validate user data completeness and format."""
        required_fields = ["name", "email", "age"]
        
        result = {
            "is_valid": True,
            "missing_fields": [],
            "validation_errors": []
        }
        
        # Check required fields
        for field in required_fields:
            if field not in user_data:
                result["missing_fields"].append(field)
                result["is_valid"] = False
        
        # Validate specific fields
        if "email" in user_data:
            if not validate_email(user_data["email"]):
                result["validation_errors"].append("Invalid email format")
                result["is_valid"] = False
        
        if "age" in user_data:
            try:
                age = int(user_data["age"])
                if age < 0 or age > 150:
                    result["validation_errors"].append("Age must be between 0 and 150")
                    result["is_valid"] = False
            except (ValueError, TypeError):
                result["validation_errors"].append("Age must be a valid number")
                result["is_valid"] = False
        
        return result
    
    # Test valid user data
    valid_user = {
        "name": "John Doe",
        "email": "john@example.com",
        "age": 30,
        "city": "New York"
    }
    
    result = validate_user_data(valid_user)
    print(f"Valid user data: {result}")
    
    # Test invalid user data
    invalid_user = {
        "name": "Jane",
        "email": "invalid-email",
        "age": "not-a-number"
    }
    
    result = validate_user_data(invalid_user)
    print(f"Invalid user data: {result}")
    
    # Example 3: Numeric Validation with Caching
    print("\n🔢 Example 3: Numeric Validation (with caching)")
    print("-" * 50)
    
    @validator(name="number_validation", version="1.0.0", cache_results=True)
    def validate_positive_number(number) -> dict:
        """Validate that a number is positive (demonstrates caching)."""
        print(f"  🔍 Processing number: {number}")  # This will show caching in action
        
        try:
            num = float(number)
            return {
                "is_valid": num > 0,
                "value": num,
                "is_positive": num > 0,
                "is_integer": num == int(num) if num == int(num) else False
            }
        except (ValueError, TypeError):
            return {
                "is_valid": False,
                "error": "Not a valid number"
            }
    
    # Test numbers (notice caching behavior)
    test_numbers = [5, 5, -3, "10.5", "10.5", "invalid", 0]
    
    for number in test_numbers:
        result = validate_positive_number(number)
        print(f"Number {number}: {result}")
    
    # Example 4: Check Workspace Statistics
    print("\n📈 Example 4: Workspace Statistics")
    print("-" * 35)
    
    from runlayer import get_default_client
    client = get_default_client()
    
    stats = client.get_workspace_stats()
    print(f"Workspace: {stats['workspace_name']}")
    print(f"Total proofs created: {stats['total_proofs']}")
    print(f"Storage used: {stats.get('storage_size_mb', 0):.2f} MB")
    print(f"Local storage path: {stats['storage_path']}")
    
    # List recent proofs
    print("\n📋 Recent Validation Proofs:")
    recent_proofs = client.list_proofs(limit=5)
    
    for i, proof in enumerate(recent_proofs, 1):
        print(f"{i}. {proof.validator_name} v{proof.validator_version}")
        print(f"   Input: {proof.input_data}")
        print(f"   Output: {proof.output_data}")
        print(f"   Execution time: {proof.execution_time_ms}ms")
        print(f"   Created: {proof.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
    
    print("✨ All examples completed!")
    print("\n💡 Key takeaways:")
    print("- @validator decorator automatically creates cryptographic proofs")
    print("- Results are cached locally for identical inputs")
    print("- All proofs are stored in local SQLite database")
    print("- No internet connection required for basic usage")
    print("- Proofs include execution time, input/output hashes, and signatures")


if __name__ == "__main__":
    main()
