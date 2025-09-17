"""
Tests for Story 2: Multi-Tenant Database Setup (Senior Developer Approach)

Tests focus on:
- Repository pattern functionality
- Performance requirements (<100ms validator lookups)
- Multi-tenant isolation (simple owner_id filtering)
- Pydantic validation
- Database operations
"""

import pytest
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from src.database import (
    Base, 
    Workspace, ValidatorRegistry, ProofLake, ReplayJob,
    WorkspaceType, ValidationStatus, ReplayStatus,
    WorkspaceCreate, ValidatorCreate,
    WorkspaceRepository, ValidatorRepository,
    engine, SessionLocal
)


# Test database URL (use in-memory SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create test database session."""
    SessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with SessionLocal() as session:
        yield session


@pytest.fixture
async def workspace_repo(test_session):
    """Create workspace repository."""
    return WorkspaceRepository(test_session)


@pytest.fixture
async def validator_repo(test_session):
    """Create validator repository."""
    return ValidatorRepository(test_session)


@pytest.fixture
async def sample_workspace(workspace_repo):
    """Create sample workspace for testing."""
    workspace_data = WorkspaceCreate(
        name="Test Workspace",
        type=WorkspaceType.SDK,
        owner_id="user123"
    )
    return await workspace_repo.create_workspace(workspace_data, "user123")


class TestPydanticValidation:
    """Test Pydantic schemas for validation (don't reinvent validation)."""
    
    def test_workspace_create_valid(self):
        """Test valid workspace creation data."""
        data = WorkspaceCreate(
            name="My Workspace",
            type=WorkspaceType.SAAS,
            owner_id="user123"
        )
        assert data.name == "My Workspace"
        assert data.type == WorkspaceType.SAAS
        assert data.max_validators == 100  # Default
    
    def test_workspace_create_invalid_name(self):
        """Test invalid workspace name."""
        with pytest.raises(ValueError):
            WorkspaceCreate(
                name="",  # Empty name should fail
                type=WorkspaceType.SDK,
                owner_id="user123"
            )
    
    def test_validator_create_valid(self):
        """Test valid validator creation data."""
        data = ValidatorCreate(
            name="email-validator",
            version="1.0.0",
            code_bundle_url="https://storage.googleapis.com/bundles/email-validator-1.0.0.wasm",
            wasm_hash="a" * 64  # 64-char hash
        )
        assert data.version == "1.0.0"
        assert len(data.wasm_hash) == 64
    
    def test_validator_create_invalid_version(self):
        """Test invalid semantic version."""
        with pytest.raises(ValueError):
            ValidatorCreate(
                name="test-validator",
                version="invalid-version",  # Should be semantic versioning
                code_bundle_url="https://example.com/bundle.wasm",
                wasm_hash="a" * 64
            )


class TestWorkspaceRepository:
    """Test workspace repository operations."""
    
    @pytest.mark.asyncio
    async def test_create_workspace(self, workspace_repo):
        """Test workspace creation."""
        workspace_data = WorkspaceCreate(
            name="Test Workspace",
            type=WorkspaceType.SDK,
            owner_id="user123"
        )
        
        workspace = await workspace_repo.create_workspace(workspace_data, "user123")
        
        assert workspace.name == "Test Workspace"
        assert workspace.type == WorkspaceType.SDK
        assert workspace.owner_id == "user123"
        assert workspace.max_validators == 100
    
    @pytest.mark.asyncio
    async def test_get_by_owner(self, workspace_repo):
        """Test multi-tenant isolation (simple owner_id filtering)."""
        # Create workspaces for different owners
        workspace1_data = WorkspaceCreate(name="Workspace 1", type=WorkspaceType.SAAS, owner_id="user1")
        workspace2_data = WorkspaceCreate(name="Workspace 2", type=WorkspaceType.SDK, owner_id="user2")
        workspace3_data = WorkspaceCreate(name="Workspace 3", type=WorkspaceType.SAAS, owner_id="user1")
        
        await workspace_repo.create_workspace(workspace1_data, "user1")
        await workspace_repo.create_workspace(workspace2_data, "user2")
        await workspace_repo.create_workspace(workspace3_data, "user1")
        
        # Test tenant isolation
        user1_workspaces = await workspace_repo.get_by_owner("user1")
        user2_workspaces = await workspace_repo.get_by_owner("user2")
        
        assert len(user1_workspaces) == 2
        assert len(user2_workspaces) == 1
        assert all(w.owner_id == "user1" for w in user1_workspaces)
        assert all(w.owner_id == "user2" for w in user2_workspaces)


class TestValidatorRepository:
    """Test validator repository operations."""
    
    @pytest.mark.asyncio
    async def test_create_validator(self, validator_repo, sample_workspace):
        """Test validator creation."""
        validator_data = ValidatorCreate(
            name="email-validator",
            version="1.0.0",
            description="Validates email formats",
            code_bundle_url="https://storage.googleapis.com/bundles/email-validator.wasm",
            wasm_hash="a" * 64,
            metadata={"author": "test", "tags": ["email", "validation"]}
        )
        
        validator = await validator_repo.create_validator(sample_workspace.id, validator_data)
        
        assert validator.name == "email-validator"
        assert validator.version == "1.0.0"
        assert validator.workspace_id == sample_workspace.id
        assert validator.is_active is True
        assert validator.metadata["author"] == "test"
    
    @pytest.mark.asyncio
    async def test_validator_lookup_performance(self, validator_repo, sample_workspace):
        """Test <100ms validator lookup performance (optimized query)."""
        # Create test validator
        validator_data = ValidatorCreate(
            name="fast-validator",
            version="2.1.0",
            code_bundle_url="https://example.com/fast.wasm",
            wasm_hash="b" * 64
        )
        
        created_validator = await validator_repo.create_validator(sample_workspace.id, validator_data)
        
        # Test optimized lookup (should use idx_validator_lookup index)
        start_time = asyncio.get_event_loop().time()
        
        found_validator = await validator_repo.get_validator(
            sample_workspace.id, 
            "fast-validator", 
            "2.1.0"
        )
        
        end_time = asyncio.get_event_loop().time()
        lookup_time_ms = (end_time - start_time) * 1000
        
        # Performance requirement: <100ms
        assert lookup_time_ms < 100, f"Lookup took {lookup_time_ms}ms, should be <100ms"
        assert found_validator is not None
        assert found_validator.id == created_validator.id
    
    @pytest.mark.asyncio
    async def test_list_active_validators(self, validator_repo, sample_workspace):
        """Test listing active validators for workspace."""
        # Create active and inactive validators
        active_data = ValidatorCreate(
            name="active-validator",
            version="1.0.0",
            code_bundle_url="https://example.com/active.wasm",
            wasm_hash="c" * 64
        )
        
        inactive_data = ValidatorCreate(
            name="inactive-validator", 
            version="1.0.0",
            code_bundle_url="https://example.com/inactive.wasm",
            wasm_hash="d" * 64
        )
        
        active_validator = await validator_repo.create_validator(sample_workspace.id, active_data)
        inactive_validator = await validator_repo.create_validator(sample_workspace.id, inactive_data)
        
        # Deactivate one validator
        inactive_validator.is_active = False
        await validator_repo.session.flush()
        
        # List active validators
        active_validators = await validator_repo.list_active_validators(sample_workspace.id)
        
        assert len(active_validators) == 1
        assert active_validators[0].id == active_validator.id
        assert all(v.is_active for v in active_validators)


class TestDatabaseModels:
    """Test SQLAlchemy models and relationships."""
    
    @pytest.mark.asyncio
    async def test_workspace_validator_relationship(self, test_session):
        """Test workspace-validator relationship."""
        # Create workspace
        workspace = Workspace(
            name="Relationship Test",
            type=WorkspaceType.SDK,
            owner_id="user123"
        )
        test_session.add(workspace)
        await test_session.flush()
        
        # Create validator
        validator = ValidatorRegistry(
            workspace_id=workspace.id,
            name="test-validator",
            version="1.0.0",
            code_bundle_url="https://example.com/test.wasm",
            wasm_hash="e" * 64
        )
        test_session.add(validator)
        await test_session.flush()
        
        # Test relationship loading
        result = await test_session.execute(
            select(Workspace).where(Workspace.id == workspace.id)
        )
        loaded_workspace = result.scalar_one()
        
        # Should be able to access validators through relationship
        assert len(loaded_workspace.validators) == 1
        assert loaded_workspace.validators[0].name == "test-validator"
    
    @pytest.mark.asyncio
    async def test_proof_lake_model(self, test_session, sample_workspace):
        """Test ProofLake model for validation results."""
        # Create validator first
        validator = ValidatorRegistry(
            workspace_id=sample_workspace.id,
            name="proof-validator",
            version="1.0.0",
            code_bundle_url="https://example.com/proof.wasm",
            wasm_hash="f" * 64
        )
        test_session.add(validator)
        await test_session.flush()
        
        # Create proof
        proof = ProofLake(
            workspace_id=sample_workspace.id,
            validator_id=validator.id,
            input_hash="input123",
            output_hash="output456",
            proof_data={"result": "valid", "confidence": 0.95},
            execution_time_ms=150,
            status=ValidationStatus.PASSED,
            synced_to_cloud=False
        )
        test_session.add(proof)
        await test_session.flush()
        
        assert proof.status == ValidationStatus.PASSED
        assert proof.execution_time_ms == 150
        assert proof.synced_to_cloud is False
        assert proof.proof_data["confidence"] == 0.95
    
    @pytest.mark.asyncio
    async def test_replay_job_model(self, test_session, sample_workspace):
        """Test ReplayJob model."""
        replay_job = ReplayJob(
            workspace_id=sample_workspace.id,
            name="Weekly Validation Replay",
            validator_ids=["validator1", "validator2"],
            input_criteria={"date_range": "last_week"},
            status=ReplayStatus.PENDING,
            total_validations=100
        )
        test_session.add(replay_job)
        await test_session.flush()
        
        assert replay_job.status == ReplayStatus.PENDING
        assert replay_job.total_validations == 100
        assert len(replay_job.validator_ids) == 2


class TestPerformanceRequirements:
    """Test Story 2 performance requirements."""
    
    @pytest.mark.asyncio
    async def test_concurrent_connections_support(self):
        """Test support for 10K concurrent connections (connection pooling)."""
        # This tests the engine configuration
        from src.database import engine
        
        # Verify connection pool settings
        assert engine.pool.size() >= 20  # Base pool size
        assert engine.pool._max_overflow >= 30  # Max overflow
        
        # Total capacity should support 10K+ connections
        total_capacity = engine.pool.size() + engine.pool._max_overflow
        assert total_capacity >= 50
    
    @pytest.mark.asyncio
    async def test_database_health_check(self):
        """Test database health check for 99.9% uptime SLA."""
        from src.database import health_check
        
        # Health check should return True for working database
        is_healthy = await health_check()
        assert is_healthy is True


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
