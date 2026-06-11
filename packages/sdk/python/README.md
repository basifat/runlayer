# RunLayer Python SDK

Add validation to any Python function with a simple decorator.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Quick Start

### Installation

Not yet published to PyPI; install from the repo:

```bash
cd packages/sdk/python
pip install -e .
```

### Basic Usage

Transform any Python function into a validated function with the `@validator` decorator:

```python
from runlayer import validator

@validator(name="email_validation", version="1.0.0")
def validate_email(email: str) -> bool:
    """Validate email format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

# Usage automatically creates and stores cryptographic proofs
result = validate_email("test@example.com")  # Returns: True
print(f"Email is valid: {result}")
```

That's it! Your function now:
- **Creates cryptographic proofs** for every execution
- **Stores results locally** in SQLite (works offline)
- **Syncs to cloud** when API key is configured
- **Caches results** for identical inputs
- **Signs proofs** with Ed25519 for authenticity

## Why RunLayer?

### The Problem
- Manual validation is error-prone and time-consuming
- No standardized way to prove validation occurred
- Difficult to share and verify validation results
- No audit trail for compliance requirements

### The Solution
RunLayer makes validation as simple as adding a decorator - inspired by [Temporal](https://temporal.io/)'s approach to workflow orchestration, but for AI validation.

```python
# Before: Manual, unverified validation
def check_data(data):
    # Manual validation logic
    # No proof it happened
    # No sharing mechanism
    return is_valid

# After: Automatic proof generation
@validator(name="data_check", version="1.0.0")
def check_data(data):
    # Same validation logic
    # Automatic proof creation
    # Cryptographic signatures
    # Cloud sync and sharing
    return is_valid
```

## Core Concepts

### Validators
A **validator** is any Python function decorated with `@validator`. It automatically:
- Generates unique proofs for each execution
- Creates SHA-256 hashes of inputs and outputs
- Signs proofs with Ed25519 cryptography
- Stores everything locally and syncs to cloud

### Proofs
A **RunProof** contains:
- Input/output hashes for integrity verification
- Execution metadata (time, status, version)
- Cryptographic signature for authenticity
- Workspace isolation for multi-project support

### Workspaces
**Workspaces** provide project isolation:
- Each project gets its own local ProofLake (SQLite database)
- Independent configuration and API keys
- Separate sync and storage quotas

## Advanced Usage

### Custom Configuration

```python
from runlayer import RunLayerClient, validator

# Configure client for your project
client = RunLayerClient(
    workspace="my-ai-project",
    api_key="your-api-key",
    auto_sync=True,
    storage_path="/custom/path"
)

@validator(
    name="advanced_validation", 
    version="2.1.0",
    client=client,
    description="Advanced data validation with custom rules",
    metadata={"team": "data-science", "env": "production"}
)
def validate_advanced_data(data: dict, threshold: float = 0.8) -> dict:
    """Advanced validation with custom configuration."""
    score = calculate_quality_score(data)
    return {
        "is_valid": score >= threshold,
        "score": score,
        "timestamp": datetime.utcnow().isoformat()
    }
```

### Working with Proofs

```python
# Get validation statistics
stats = client.get_workspace_stats()
print(f"Total proofs: {stats['total_proofs']}")
print(f"Synced to cloud: {stats['synced_proofs']}")

# List recent proofs
proofs = client.list_proofs(limit=10)
for proof in proofs:
    print(f"Proof {proof.id}: {proof.validator_name} v{proof.validator_version}")

# Get specific proof
proof = client.get_proof("proof-id-here")
if proof and proof.is_valid():
    print(f"Proof is valid and signed: {proof.signature}")
```

### Cloud Synchronization

```python
import asyncio

async def sync_example():
    # Manual sync to cloud
    result = await client.sync_to_cloud()
    print(f"Synced {result['synced_count']} proofs")
    
    # Download shared proofs
    shared_proofs = await client.download_shared_proofs()
    print(f"Downloaded {len(shared_proofs)} shared proofs")

# Run async operations
asyncio.run(sync_example())
```

## Configuration Options

### Environment Variables

```bash
# Optional: Configure default settings
export RUNLAYER_API_KEY="your-api-key"
export RUNLAYER_WORKSPACE="default"
export RUNLAYER_AUTO_SYNC="true"
export RUNLAYER_STORAGE_PATH="~/.runlayer"
```

### Workspace Configuration

```python
client = RunLayerClient(
    workspace="my-project",           # Project name
    api_key="your-api-key",          # For cloud sync
    auto_sync=True,                  # Auto sync to cloud
    storage_path="/custom/path",     # Local storage location
    max_storage_mb=500,              # Storage quota
    sync_interval_seconds=300,       # Sync frequency
    encrypt_local_storage=True,      # Encrypt SQLite DB
    batch_sync_size=50              # Proofs per sync batch
)
```

## Security Features

### Cryptographic Signatures
- **Ed25519 signatures** for all proofs
- **SHA-256 hashing** of inputs and outputs
- **Tamper-proof** proof generation
- **Key management** handled automatically

### Data Protection
- **Local encryption** of SQLite databases
- **Secure API key** storage
- **No sensitive data** in logs
- **GDPR-compliant** data handling

## Performance

### Benchmarks
- **<50ms decorator overhead** for typical functions
- **<100ms local storage** operations
- **Efficient batching** for cloud sync
- **<50MB memory usage** for typical workloads

### Optimization Tips
```python
# Enable result caching for expensive validations
@validator(name="expensive_check", version="1.0.0", cache_results=True)
def expensive_validation(data):
    # Expensive computation here
    return result

# Disable auto-sync for high-frequency validations
@validator(name="high_freq", version="1.0.0")
def high_frequency_validation(data):
    # Will sync in batches automatically
    return result
```

## Testing Your Validators

```python
import pytest
from runlayer import validator, get_validator_info

@validator(name="test_validator", version="1.0.0")
def my_validator(x: int) -> bool:
    return x > 0

def test_validator_functionality():
    # Test the validation logic
    assert my_validator(5) == True
    assert my_validator(-1) == False

def test_validator_metadata():
    # Test validator configuration
    config = get_validator_info(my_validator)
    assert config.name == "test_validator"
    assert config.version == "1.0.0"

def test_proof_creation():
    # Test proof creation
    from runlayer import get_default_client
    client = get_default_client()
    
    # Execute validator
    result = my_validator(10)
    
    # Check proof was created
    proofs = client.list_proofs(validator_name="test_validator", limit=1)
    assert len(proofs) > 0
    assert proofs[0].output_data == True
```

## Migration & Versioning

### Semantic Versioning
```python
# Version 1.0.0 - Initial implementation
@validator(name="data_check", version="1.0.0")
def validate_data_v1(data):
    return basic_validation(data)

# Version 2.0.0 - Breaking changes
@validator(name="data_check", version="2.0.0")
def validate_data_v2(data):
    return enhanced_validation(data)  # Different output format
```

### Backward Compatibility
```python
# Support multiple versions simultaneously
@validator(name="legacy_check", version="1.0.0")
def legacy_validator(data):
    return old_format_result(data)

@validator(name="legacy_check", version="2.0.0")  
def modern_validator(data):
    return new_format_result(data)
```

## Production Deployment

### Docker Integration
```dockerfile
FROM python:3.11-slim

# Install RunLayer SDK (from a checkout of this repo)
COPY packages/sdk/python /opt/runlayer-sdk
RUN pip install /opt/runlayer-sdk

# Copy your validation code
COPY validators/ /app/validators/

# Set environment variables
ENV RUNLAYER_API_KEY="your-production-key"
ENV RUNLAYER_WORKSPACE="production"

WORKDIR /app
CMD ["python", "validators/main.py"]
```

### CI/CD Integration
```yaml
# GitHub Actions example
name: Validation Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -e packages/sdk/python pytest
        
    - name: Run validation tests
      run: |
        pytest validators/
        
    - name: Sync proofs to cloud
      env:
        RUNLAYER_API_KEY: ${{ secrets.RUNLAYER_API_KEY }}
      run: |
        python -c "
        import asyncio
        from runlayer import RunLayerClient
        
        async def sync():
            client = RunLayerClient(workspace='ci-cd')
            result = await client.sync_to_cloud()
            print(f'Synced {result[\"synced_count\"]} proofs')
        
        asyncio.run(sync())
        "
```

## Troubleshooting

### Common Issues

**Import Error**
```python
# Problem: ModuleNotFoundError: No module named 'runlayer'
# Solution: Install the package from the repo
pip install -e packages/sdk/python
```

**Permission Error**
```python
# Problem: Permission denied writing to ~/.runlayer
# Solution: Use custom storage path
client = RunLayerClient(storage_path="/tmp/runlayer")
```

**Sync Failures**
```python
# Problem: Proofs not syncing to cloud
# Solution: Check API key and connection
client = RunLayerClient(api_key="your-key")
is_connected = await client.test_connection()
print(f"Connected: {is_connected}")
```

### Debug Mode
```python
import logging
from runlayer.utils.logging import setup_logging

# Enable debug logging
setup_logging(level="DEBUG", json_format=False)

# Your validator code here
@validator(name="debug_test", version="1.0.0")
def debug_validator(data):
    return data
```

## API Reference

### Core Classes

- **`@validator`** - Main decorator for creating validated functions
- **`RunLayerClient`** - Client for workspace and proof management
- **`RunProof`** - Model representing a validation proof
- **`Workspace`** - Model for project isolation and configuration

### Utility Functions

- **`get_default_client()`** - Get the default RunLayer client
- **`get_validator_info(func)`** - Get validator configuration from decorated function
- **`is_validator(func)`** - Check if function is decorated with @validator

## Development Setup

```bash
git clone https://github.com/basifat/runlayer.git
cd runlayer/packages/sdk/python
pip install -e .
pytest
```

## License

This project is licensed under the MIT License - see the repository [LICENSE](../../../LICENSE) file for details.

---

*Transform any Python function into a validated, cryptographically signed, and shareable proof of execution.*
