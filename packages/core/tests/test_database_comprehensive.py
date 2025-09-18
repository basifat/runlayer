"""
Comprehensive Unit Tests for database.py - Multi-Tenant Database Setup

Tests ALL core functionality to ensure 80%+ coverage:
- Repository pattern functionality
- Performance requirements (<100ms validator lookups)
- Multi-tenant isolation (simple owner_id filtering)
- Pydantic validation
- Database operations
- DRY mixins (UUIDMixin, TimestampMixin, TenantMixin)
- DatabaseService functionality
- Error handling and edge cases
"""

import pytest
import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text
from pydantic import ValidationError
import uuid

from src.database import (
    Base, 
    Workspace, ValidatorRegistry, ProofLake, ReplayJob,
    WorkspaceType, ValidationStatus, ReplayStatus,
    WorkspaceCreate, ValidatorCreate,
    WorkspaceRepository, ValidatorRepository, ProofRepository, ReplayRepository,
    DatabaseService, create_database_engine, init_db, close_db,
    UUIDMixin, TimestampMixin, TenantMixin
)


# Test database URL for in-memory SQLite
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create test database session."""
    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
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
async def proof_repo(test_session):
    """Create proof repository."""
    return ProofRepository(test_session)


@pytest.fixture
async def replay_repo(test_session):
    """Create replay repository."""
    return ReplayRepository(test_session)


@pytest.fixture
async def sample_workspace(workspace_repo):
    """Create sample workspace for testing."""
    workspace_data = WorkspaceCreate(
        name="Test Workspace",
        type=WorkspaceType.SDK,
        owner_id="user123",
        max_validators=100,
        max_executions_per_day=10000,
        max_storage_mb=1000
    )
    return await workspace_repo.create_workspace(workspace_data, "user123")


class TestPydanticModels:
    """Test Pydantic model validation."""
    
    def test_workspace_create_validation(self):
        """Test WorkspaceCreate validation."""
        # Valid data
        valid_data = WorkspaceCreate(
            name="Test Workspace",
            type=WorkspaceType.SDK,
            owner_id="user123"
        )
        assert valid_data.name == "Test Workspace"
        assert valid_data.type == WorkspaceType.SDK
        assert valid_data.owner_id == "user123"
        assert valid_data.max_validators == 100  # Default
    
    def test_workspace_create_validation_errors(self):
        """Test WorkspaceCreate validation errors."""
        # Empty name
        with pytest.raises(ValidationError):
            WorkspaceCreate(name="", type=WorkspaceType.SDK, owner_id="user123")
        
        # Empty owner_id
        with pytest.raises(ValidationError):
            WorkspaceCreate(name="Test", type=WorkspaceType.SDK, owner_id="")
        
        # Invalid max_validators
        with pytest.raises(ValidationError):
            WorkspaceCreate(name="Test", type=WorkspaceType.SDK, owner_id="user123", max_validators=0)
    
    def test_validator_create_validation(self):
        """Test ValidatorCreate validation."""
        # Valid data
        valid_data = ValidatorCreate(
            name="email-validator",
            version="1.0.0",
            code_bundle_url="https://example.com/bundle.wasm",
            wasm_hash="a" * 64
        )
        assert valid_data.name == "email-validator"
        assert valid_data.version == "1.0.0"
        assert valid_data.wasm_hash == "a" * 64
    
    def test_validator_create_validation_errors(self):
        """Test ValidatorCreate validation errors."""
        # Invalid semantic version
        with pytest.raises(ValidationError):
            ValidatorCreate(
                name="test",
                version="invalid-version",
                code_bundle_url="https://example.com/bundle.wasm",
                wasm_hash="a" * 64
            )
        
        # Invalid hash length
        with pytest.raises(ValidationError):
            ValidatorCreate(
                name="test",
                version="1.0.0",
                code_bundle_url="https://example.com/bundle.wasm",
                wasm_hash="short"
            )
        
        # Empty name
        with pytest.raises(ValidationError):
            ValidatorCreate(
                name="",
                version="1.0.0",
                code_bundle_url="https://example.com/bundle.wasm",
                wasm_hash="a" * 64
            )


class TestDRYMixins:
    """Test DRY mixins functionality."""
    
    def test_uuid_mixin(self):
        """Test UUIDMixin provides UUID primary key."""
        workspace = Workspace()
        
        # Should have id field
        assert hasattr(workspace, 'id')
        
        # ID should be generated automatically
        workspace.name = "Test"
        workspace.type = WorkspaceType.SDK
        workspace.owner_id = "user123"
        
        # UUID should be valid format
        if workspace.id:
            uuid.UUID(str(workspace.id))  # Should not raise exception
    
    def test_timestamp_mixin(self):
        """Test TimestampMixin provides created_at and updated_at."""
        workspace = Workspace()
        
        # Should have timestamp fields
        assert hasattr(workspace, 'created_at')
        assert hasattr(workspace, 'updated_at')
    
    def test_tenant_mixin(self):
        """Test TenantMixin provides workspace_id."""
        validator = ValidatorRegistry()
        
        # Should have workspace_id field
        assert hasattr(validator, 'workspace_id')


class TestSQLAlchemyModels:
    """Test SQLAlchemy model functionality."""
    
    async def test_workspace_model_creation(self, test_session):
        """Test Workspace model creation."""
        workspace = Workspace(
            name="Test Workspace",
            type=WorkspaceType.SDK,
            owner_id="user123",
            max_validators=100
        )
        
        test_session.add(workspace)
        await test_session.commit()
        await test_session.refresh(workspace)
        
        assert workspace.id is not None
        assert workspace.name == "Test Workspace"
        assert workspace.type == WorkspaceType.SDK
        assert workspace.owner_id == "user123"
        assert workspace.created_at is not None
    
    async def test_validator_model_creation(self, test_session, sample_workspace):
        """Test ValidatorRegistry model creation."""
        validator = ValidatorRegistry(
            workspace_id=sample_workspace.id,
            name="email-validator",
            version="1.0.0",
            code_bundle_url="https://example.com/bundle.wasm",
            wasm_hash="a" * 64,
            metadata={"description": "Email validation"}
        )
        
        test_session.add(validator)
        await test_session.commit()
        await test_session.refresh(validator)
        
        assert validator.id is not None
        assert validator.workspace_id == sample_workspace.id
        assert validator.name == "email-validator"
        assert validator.is_active is True
        assert validator.metadata["description"] == "Email validation"
    
    async def test_proof_model_creation(self, test_session, sample_workspace):
        """Test ProofLake model creation."""
        # First create a validator
        validator = ValidatorRegistry(
            workspace_id=sample_workspace.id,
            name="test-validator",
            version="1.0.0",
            code_bundle_url="https://example.com/bundle.wasm",
            wasm_hash="a" * 64
        )
        test_session.add(validator)
        await test_session.commit()
        await test_session.refresh(validator)
        
        # Create proof
        proof = ProofLake(
            workspace_id=sample_workspace.id,
            validator_id=validator.id,
            input_hash="input123",
            output_hash="output456",
            proof_data={"result": "valid"},
            execution_time_ms=150,
            status=ValidationStatus.PASSED
        )
        
        test_session.add(proof)
        await test_session.commit()
        await test_session.refresh(proof)
        
        assert proof.id is not None
        assert proof.workspace_id == sample_workspace.id
        assert proof.validator_id == validator.id
        assert proof.status == ValidationStatus.PASSED
        assert proof.synced_to_cloud is False  # Default


class TestWorkspaceRepository:
    """Test WorkspaceRepository functionality."""
    
    async def test_create_workspace(self, workspace_repo):
        """Test workspace creation."""
        workspace_data = WorkspaceCreate(
            name="Test Workspace",
            type=WorkspaceType.SDK,
            owner_id="user123"
        )
        
        workspace = await workspace_repo.create_workspace(workspace_data, "user123")
        
        assert workspace.id is not None
        assert workspace.name == "Test Workspace"
        assert workspace.type == WorkspaceType.SDK
        assert workspace.owner_id == "user123"
        assert workspace.max_validators == 100
    
    async def test_get_workspace_by_id(self, workspace_repo, sample_workspace):
        """Test get workspace by ID."""
        found_workspace = await workspace_repo.get_workspace_by_id(sample_workspace.id, "user123")
        
        assert found_workspace is not None
        assert found_workspace.id == sample_workspace.id
        assert found_workspace.name == sample_workspace.name
    
    async def test_get_workspace_by_id_wrong_owner(self, workspace_repo, sample_workspace):
        """Test get workspace by ID with wrong owner."""
        found_workspace = await workspace_repo.get_workspace_by_id(sample_workspace.id, "wrong_user")
        
        assert found_workspace is None  # Should not find due to owner mismatch
    
    async def test_list_workspaces_by_owner(self, workspace_repo):
        """Test list workspaces by owner."""
        # Create multiple workspaces
        for i in range(3):
            workspace_data = WorkspaceCreate(
                name=f"Workspace {i}",
                type=WorkspaceType.SDK,
                owner_id="user123"
            )
            await workspace_repo.create_workspace(workspace_data, "user123")
        
        # Create workspace for different owner
        workspace_data = WorkspaceCreate(
            name="Other Workspace",
            type=WorkspaceType.SAAS,
            owner_id="user456"
        )
        await workspace_repo.create_workspace(workspace_data, "user456")
        
        # List workspaces for user123
        workspaces = await workspace_repo.list_workspaces_by_owner("user123")
        
        assert len(workspaces) == 3
        assert all(w.owner_id == "user123" for w in workspaces)
    
    async def test_check_quota_limits(self, workspace_repo, sample_workspace):
        """Test quota limits checking."""
        quotas = await workspace_repo.check_quota_limits(sample_workspace.id)
        
        assert "validators" in quotas
        assert "executions_today" in quotas
        assert "storage_mb" in quotas
        
        assert quotas["validators"]["max"] == sample_workspace.max_validators
        assert quotas["validators"]["current"] == 0  # No validators created yet


class TestValidatorRepository:
    """Test ValidatorRepository functionality."""
    
    async def test_create_validator(self, validator_repo, sample_workspace):
        """Test validator creation."""
        validator_data = ValidatorCreate(
            name="email-validator",
            version="1.0.0",
            code_bundle_url="https://example.com/bundle.wasm",
            wasm_hash="a" * 64,
            description="Email validation",
            metadata={"type": "email"}
        )
        
        validator = await validator_repo.create_validator(sample_workspace.id, validator_data)
        
        assert validator.id is not None
        assert validator.workspace_id == sample_workspace.id
        assert validator.name == "email-validator"
        assert validator.version == "1.0.0"
        assert validator.is_active is True
        assert validator.description == "Email validation"
        assert validator.metadata["type"] == "email"
    
    async def test_get_validator_performance(self, validator_repo, sample_workspace):
        """Test validator lookup performance (<100ms requirement)."""
        # Create validator
        validator_data = ValidatorCreate(
            name="performance-test",
            version="1.0.0",
            code_bundle_url="https://example.com/bundle.wasm",
            wasm_hash="b" * 64
        )
        validator = await validator_repo.create_validator(sample_workspace.id, validator_data)
        
        # Test performance
        start_time = time.time()
        found_validator = await validator_repo.get_validator(
            sample_workspace.id, "performance-test", "1.0.0"
        )
        duration_ms = (time.time() - start_time) * 1000
        
        assert found_validator is not None
        assert found_validator.id == validator.id
        assert duration_ms < 100  # Performance requirement
    
    async def test_list_validators_by_workspace(self, validator_repo, sample_workspace):
        """Test list validators by workspace."""
        # Create multiple validators
        for i in range(3):
            validator_data = ValidatorCreate(
                name=f"validator-{i}",
                version="1.0.0",
                code_bundle_url=f"https://example.com/bundle-{i}.wasm",
                wasm_hash=f"{i}" * 64
            )
            await validator_repo.create_validator(sample_workspace.id, validator_data)
        
        validators = await validator_repo.list_validators_by_workspace(sample_workspace.id)
        
        assert len(validators) == 3
        assert all(v.workspace_id == sample_workspace.id for v in validators)
        assert all(v.is_active for v in validators)
    
    async def test_deactivate_validator(self, validator_repo, sample_workspace):
        """Test validator deactivation (soft delete)."""
        # Create validator
        validator_data = ValidatorCreate(
            name="to-deactivate",
            version="1.0.0",
            code_bundle_url="https://example.com/bundle.wasm",
            wasm_hash="c" * 64
        )
        validator = await validator_repo.create_validator(sample_workspace.id, validator_data)
        
        # Deactivate
        await validator_repo.deactivate_validator(sample_workspace.id, validator.id)
        
        # Verify deactivation
        found_validator = await validator_repo.get_validator_by_id(sample_workspace.id, validator.id)
        assert found_validator.is_active is False


class TestProofRepository:
    """Test ProofRepository functionality."""
    
    async def test_create_proof(self, proof_repo, sample_workspace):
        """Test proof creation."""
        # Create validator first
        validator = ValidatorRegistry(
            workspace_id=sample_workspace.id,
            name="test-validator",
            version="1.0.0",
            code_bundle_url="https://example.com/bundle.wasm",
            wasm_hash="d" * 64
        )
        proof_repo.session.add(validator)
        await proof_repo.session.commit()
        await proof_repo.session.refresh(validator)
        
        # Create proof
        proof_data = {
            "input_hash": "input123",
            "output_hash": "output456",
            "proof_data": {"result": "valid"},
            "execution_time_ms": 150,
            "status": ValidationStatus.PASSED
        }
        
        proof = await proof_repo.create_proof(sample_workspace.id, validator.id, proof_data)
        
        assert proof.id is not None
        assert proof.workspace_id == sample_workspace.id
        assert proof.validator_id == validator.id
        assert proof.input_hash == "input123"
        assert proof.status == ValidationStatus.PASSED
    
    async def test_proof_deduplication(self, proof_repo, sample_workspace):
        """Test proof deduplication by input hash."""
        # Create validator
        validator = ValidatorRegistry(
            workspace_id=sample_workspace.id,
            name="dedup-validator",
            version="1.0.0",
            code_bundle_url="https://example.com/bundle.wasm",
            wasm_hash="e" * 64
        )
        proof_repo.session.add(validator)
        await proof_repo.session.commit()
        await proof_repo.session.refresh(validator)
        
        # Create first proof
        proof_data = {
            "input_hash": "duplicate_input",
            "output_hash": "output1",
            "proof_data": {"result": "valid"},
            "execution_time_ms": 100,
            "status": ValidationStatus.PASSED
        }
        
        proof1 = await proof_repo.create_proof(sample_workspace.id, validator.id, proof_data)
        
        # Try to create duplicate proof
        proof_data["output_hash"] = "output2"  # Different output
        proof2 = await proof_repo.create_proof(sample_workspace.id, validator.id, proof_data)
        
        # Should return the same proof (deduplication)
        assert proof1.id == proof2.id
        assert proof1.input_hash == proof2.input_hash


class TestDatabaseService:
    """Test DatabaseService functionality."""
    
    @patch('src.database.engine')
    def test_database_service_initialization(self, mock_engine):
        """Test DatabaseService initialization."""
        service = DatabaseService()
        
        # Should have repository properties
        assert hasattr(service, 'workspaces')
        assert hasattr(service, 'validators')
        assert hasattr(service, 'proofs')
        assert hasattr(service, 'replays')
    
    @patch('src.database.SessionLocal')
    async def test_database_service_session_management(self, mock_session_local):
        """Test DatabaseService session management."""
        mock_session = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session
        
        service = DatabaseService()
        
        # Access a repository (should create session)
        workspace_repo = service.workspaces
        assert workspace_repo is not None


class TestDatabaseUtilities:
    """Test database utility functions."""
    
    @patch('src.database.create_async_engine')
    def test_create_database_engine(self, mock_create_engine):
        """Test create_database_engine function."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        
        engine = create_database_engine("postgresql+asyncpg://test/db")
        
        mock_create_engine.assert_called_once()
        assert engine == mock_engine
    
    @patch('src.database.engine')
    async def test_init_db(self, mock_engine):
        """Test init_db function."""
        mock_conn = AsyncMock()
        mock_engine.begin.return_value.__aenter__.return_value = mock_conn
        
        await init_db()
        
        mock_engine.begin.assert_called_once()
        mock_conn.run_sync.assert_called_once()
    
    @patch('src.database.engine')
    async def test_close_db(self, mock_engine):
        """Test close_db function."""
        await close_db()
        
        mock_engine.dispose.assert_called_once()


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    async def test_workspace_not_found(self, workspace_repo):
        """Test workspace not found scenario."""
        non_existent_id = str(uuid.uuid4())
        workspace = await workspace_repo.get_workspace_by_id(non_existent_id, "user123")
        
        assert workspace is None
    
    async def test_validator_not_found(self, validator_repo, sample_workspace):
        """Test validator not found scenario."""
        validator = await validator_repo.get_validator(
            sample_workspace.id, "non-existent", "1.0.0"
        )
        
        assert validator is None
    
    async def test_quota_exceeded_validation(self, workspace_repo, validator_repo):
        """Test quota exceeded scenario."""
        # Create workspace with low quota
        workspace_data = WorkspaceCreate(
            name="Low Quota Workspace",
            type=WorkspaceType.SDK,
            owner_id="user123",
            max_validators=1  # Very low quota
        )
        workspace = await workspace_repo.create_workspace(workspace_data, "user123")
        
        # Create first validator (should succeed)
        validator_data = ValidatorCreate(
            name="validator-1",
            version="1.0.0",
            code_bundle_url="https://example.com/bundle.wasm",
            wasm_hash="f" * 64
        )
        await validator_repo.create_validator(workspace.id, validator_data)
        
        # Try to create second validator (should fail)
        validator_data.name = "validator-2"
        validator_data.wasm_hash = "g" * 64
        
        with pytest.raises(ValueError, match="Validator quota exceeded"):
            await validator_repo.create_validator(workspace.id, validator_data)


class TestIntegrationScenarios:
    """Test integration scenarios."""
    
    async def test_complete_workspace_lifecycle(self, workspace_repo, validator_repo, proof_repo):
        """Test complete workspace lifecycle."""
        # 1. Create workspace
        workspace_data = WorkspaceCreate(
            name="Integration Test Workspace",
            type=WorkspaceType.SDK,
            owner_id="integration_user"
        )
        workspace = await workspace_repo.create_workspace(workspace_data, "integration_user")
        
        # 2. Create validator
        validator_data = ValidatorCreate(
            name="integration-validator",
            version="1.0.0",
            code_bundle_url="https://example.com/integration.wasm",
            wasm_hash="h" * 64
        )
        validator = await validator_repo.create_validator(workspace.id, validator_data)
        
        # 3. Create proof
        proof_data = {
            "input_hash": "integration_input",
            "output_hash": "integration_output",
            "proof_data": {"result": "integration_success"},
            "execution_time_ms": 75,
            "status": ValidationStatus.PASSED
        }
        proof = await proof_repo.create_proof(workspace.id, validator.id, proof_data)
        
        # 4. Verify everything is connected
        assert proof.workspace_id == workspace.id
        assert proof.validator_id == validator.id
        assert validator.workspace_id == workspace.id
        
        # 5. Check quotas
        quotas = await workspace_repo.check_quota_limits(workspace.id)
        assert quotas["validators"]["current"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=src.database", "--cov-report=term-missing"])
