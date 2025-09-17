"""
RunLayer Database - 12-Factor App + DRY Principles

12-Factor App Compliance:
- III. Config: All database config from environment
- IV. Backing Services: Database as attached resource
- VI. Processes: Stateless, share-nothing architecture
- XII. Admin Processes: Migration and admin tasks separate

DRY Principles Applied:
- Single source of truth for common operations
- Centralized base classes and mixins
- Reusable patterns across repositories
- No code duplication
"""

from typing import Optional, AsyncGenerator, TypeVar, Generic, Type, Any, Dict
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
from functools import wraps
import uuid
import logging

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, declared_attr
from sqlalchemy import String, Integer, DateTime, Boolean, Text, JSON, Index, ForeignKey, select, event
from sqlalchemy.dialects.postgresql import UUID
from pydantic import BaseModel, Field, validator

from .config import settings

# Type variables for generic repository
ModelType = TypeVar("ModelType", bound="BaseModel")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

# Logger setup (12-Factor: Logs as event streams)
logger = logging.getLogger(__name__)


# DRY: Common mixins and base classes
class TimestampMixin:
    """DRY: Reusable timestamp fields for all models."""
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )


class UUIDMixin:
    """DRY: Reusable UUID primary key for all models."""
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )


class TenantMixin:
    """DRY: Multi-tenant isolation mixin."""
    
    @declared_attr
    def workspace_id(cls) -> Mapped[str]:
        return mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)


class Base(DeclarativeBase):
    """Base class for all database models with common functionality."""
    
    def to_dict(self) -> Dict[str, Any]:
        """DRY: Convert model to dictionary (reusable across all models)."""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """DRY: Update model from dictionary (reusable across all models)."""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


# Enums for type safety (established pattern)
class WorkspaceType(str, Enum):
    SAAS = "saas"
    SDK = "sdk"

class ValidationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"

class ReplayStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# Pydantic schemas for validation (don't reinvent validation)
class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: WorkspaceType
    owner_id: str = Field(..., min_length=1)
    max_validators: int = Field(default=100, ge=1)
    max_executions_per_day: int = Field(default=10000, ge=1)
    max_storage_mb: int = Field(default=1000, ge=1)

class ValidatorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    version: str = Field(..., pattern=r'^\d+\.\d+\.\d+$')  # Semantic versioning
    description: Optional[str] = None
    code_bundle_url: str = Field(..., min_length=1)
    wasm_hash: str = Field(..., min_length=64, max_length=64)
    validator_metadata: dict = Field(default_factory=dict)


# SQLAlchemy models (use framework properly)
class Workspace(Base, UUIDMixin, TimestampMixin):
    """Multi-tenant workspace using DRY mixins."""
    __tablename__ = "workspaces"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[WorkspaceType] = mapped_column(String(50), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # Quotas with environment-configurable defaults
    max_validators: Mapped[int] = mapped_column(Integer, default=100)
    max_executions_per_day: Mapped[int] = mapped_column(Integer, default=10000)
    max_storage_mb: Mapped[int] = mapped_column(Integer, default=1000)
    
    # Relationships (DRY: consistent relationship patterns)
    validators: Mapped[list["ValidatorRegistry"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    proofs: Mapped[list["ProofLake"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    replay_jobs: Mapped[list["ReplayJob"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_workspace_owner_type', 'owner_id', 'type'),
    )


class ValidatorRegistry(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Validator registry using DRY mixins."""
    __tablename__ = "validator_registry"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Code storage
    code_bundle_url: Mapped[str] = mapped_column(String(500), nullable=False)
    wasm_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    validator_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Lifecycle
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships (DRY: consistent patterns)
    workspace: Mapped["Workspace"] = relationship(back_populates="validators")
    proofs: Mapped[list["ProofLake"]] = relationship(
        back_populates="validator", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index('idx_validator_lookup', 'workspace_id', 'name', 'version', 'is_active'),
        Index('idx_validator_workspace_active', 'workspace_id', 'is_active'),
    )


class ProofLake(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Validation results using DRY mixins."""
    __tablename__ = "proof_lake"
    
    validator_id: Mapped[str] = mapped_column(ForeignKey("validator_registry.id"), nullable=False, index=True)
    
    # Core proof data
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    output_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    proof_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Execution metadata
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ValidationStatus] = mapped_column(String(50), nullable=False)
    
    # SDK sync tracking
    synced_to_cloud: Mapped[bool] = mapped_column(Boolean, default=False)
    sync_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Relationships (DRY: consistent patterns)
    workspace: Mapped["Workspace"] = relationship(back_populates="proofs")
    validator: Mapped["ValidatorRegistry"] = relationship(back_populates="proofs")
    
    __table_args__ = (
        Index('idx_proof_workspace_created', 'workspace_id', 'created_at'),
        Index('idx_proof_sync_pending', 'workspace_id', 'synced_to_cloud'),
    )


class ReplayJob(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Replay job tracking using DRY mixins."""
    __tablename__ = "replay_jobs"
    
    # Job configuration
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    validator_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    input_criteria: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Job status and progress
    status: Mapped[ReplayStatus] = mapped_column(String(50), default=ReplayStatus.PENDING)
    total_validations: Mapped[int] = mapped_column(Integer, default=0)
    completed_validations: Mapped[int] = mapped_column(Integer, default=0)
    failed_validations: Mapped[int] = mapped_column(Integer, default=0)
    
    # Additional timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Relationships (DRY: consistent patterns)
    workspace: Mapped["Workspace"] = relationship(back_populates="replay_jobs")
    
    __table_args__ = (
        Index('idx_replay_workspace_status', 'workspace_id', 'status'),
        Index('idx_replay_created', 'created_at'),
    )


# 12-Factor App: Database as backing service with environment config
def create_database_engine() -> AsyncEngine:
    """Create database engine with 12-Factor App configuration."""
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.ENVIRONMENT == "development",
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=True,
        # 12-Factor: Logs as event streams
        logging_name="runlayer.database",
    )


# Global engine instance (12-Factor: stateless processes)
engine = create_database_engine()

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# DRY: Generic repository pattern with type safety
class BaseRepository(Generic[ModelType], ABC):
    """DRY: Generic base repository eliminating code duplication."""
    
    def __init__(self, session: AsyncSession, model_class: Type[ModelType]):
        self.session = session
        self.model_class = model_class
    
    async def get_by_id(self, id: str) -> Optional[ModelType]:
        """DRY: Generic get by ID for all models."""
        result = await self.session.execute(
            select(self.model_class).where(self.model_class.id == id)
        )
        return result.scalar_one_or_none()
    
    async def create(self, entity: ModelType) -> ModelType:
        """DRY: Generic create for all models."""
        self.session.add(entity)
        await self.session.flush()
        logger.info(f"Created {self.model_class.__name__} with id {entity.id}")
        return entity
    
    async def update(self, entity: ModelType) -> ModelType:
        """DRY: Generic update for all models."""
        await self.session.flush()
        logger.info(f"Updated {self.model_class.__name__} with id {entity.id}")
        return entity
    
    async def delete(self, entity: ModelType) -> None:
        """DRY: Generic delete for all models."""
        await self.session.delete(entity)
        await self.session.flush()
        logger.info(f"Deleted {self.model_class.__name__} with id {entity.id}")
    
    async def list_by_workspace(self, workspace_id: str) -> list[ModelType]:
        """DRY: Generic multi-tenant listing (if model has workspace_id)."""
        if hasattr(self.model_class, 'workspace_id'):
            result = await self.session.execute(
                select(self.model_class).where(self.model_class.workspace_id == workspace_id)
            )
            return result.scalars().all()
        else:
            raise NotImplementedError(f"{self.model_class.__name__} is not tenant-scoped")
    
    async def count_by_workspace(self, workspace_id: str) -> int:
        """DRY: Generic count for quota enforcement."""
        if hasattr(self.model_class, 'workspace_id'):
            from sqlalchemy import func
            result = await self.session.execute(
                select(func.count(self.model_class.id)).where(
                    self.model_class.workspace_id == workspace_id
                )
            )
            return result.scalar()
        else:
            raise NotImplementedError(f"{self.model_class.__name__} is not tenant-scoped")


class WorkspaceRepository(BaseRepository[Workspace]):
    """Workspace repository with DRY base functionality."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Workspace)
    
    async def get_by_owner(self, owner_id: str) -> list[Workspace]:
        """Get workspaces by owner (multi-tenant isolation)."""
        result = await self.session.execute(
            select(Workspace).where(Workspace.owner_id == owner_id)
        )
        return result.scalars().all()
    
    async def create_workspace(self, workspace_data: WorkspaceCreate, owner_id: str) -> Workspace:
        """Create workspace with Pydantic validation."""
        workspace = Workspace(
            name=workspace_data.name,
            type=workspace_data.type,
            owner_id=owner_id,
            max_validators=workspace_data.max_validators,
            max_executions_per_day=workspace_data.max_executions_per_day,
            max_storage_mb=workspace_data.max_storage_mb
        )
        return await self.create(workspace)
    
    async def check_quota_limits(self, workspace_id: str) -> Dict[str, Any]:
        """Check current usage against quotas."""
        workspace = await self.get_by_id(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")
        
        # Use DRY count methods from other repositories
        validator_count = await ValidatorRepository(self.session).count_by_workspace(workspace_id)
        proof_count = await ProofLakeRepository(self.session).count_by_workspace(workspace_id)
        
        return {
            "validators": {"current": validator_count, "max": workspace.max_validators},
            "proofs": {"current": proof_count, "max": workspace.max_executions_per_day},
            "storage_mb": {"current": 0, "max": workspace.max_storage_mb}  # TODO: Calculate actual usage
        }


class ValidatorRepository(BaseRepository[ValidatorRegistry]):
    """Validator repository with DRY base functionality."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, ValidatorRegistry)
    
    async def get_validator(self, workspace_id: str, name: str, version: str) -> Optional[ValidatorRegistry]:
        """Optimized validator lookup for <100ms performance."""
        result = await self.session.execute(
            select(ValidatorRegistry).where(
                ValidatorRegistry.workspace_id == workspace_id,
                ValidatorRegistry.name == name,
                ValidatorRegistry.version == version,
                ValidatorRegistry.is_active == True
            )
        )
        return result.scalar_one_or_none()
    
    async def list_active_validators(self, workspace_id: str) -> list[ValidatorRegistry]:
        """List active validators (uses DRY base method with filter)."""
        result = await self.session.execute(
            select(ValidatorRegistry).where(
                ValidatorRegistry.workspace_id == workspace_id,
                ValidatorRegistry.is_active == True
            )
        )
        return result.scalars().all()
    
    async def create_validator(self, workspace_id: str, validator_data: ValidatorCreate) -> ValidatorRegistry:
        """Create validator with Pydantic validation and quota check."""
        # Check quota before creation (DRY: reuse workspace repository)
        workspace_repo = WorkspaceRepository(self.session)
        quotas = await workspace_repo.check_quota_limits(workspace_id)
        
        if quotas["validators"]["current"] >= quotas["validators"]["max"]:
            raise ValueError(f"Validator quota exceeded for workspace {workspace_id}")
        
        validator = ValidatorRegistry(
            workspace_id=workspace_id,
            name=validator_data.name,
            version=validator_data.version,
            description=validator_data.description,
            code_bundle_url=validator_data.code_bundle_url,
            wasm_hash=validator_data.wasm_hash,
            metadata=validator_data.metadata
        )
        return await self.create(validator)
    
    async def deactivate_validator(self, validator_id: str) -> ValidatorRegistry:
        """Deactivate validator (soft delete)."""
        validator = await self.get_by_id(validator_id)
        if not validator:
            raise ValueError(f"Validator {validator_id} not found")
        
        validator.is_active = False
        return await self.update(validator)


class ProofLakeRepository(BaseRepository[ProofLake]):
    """ProofLake repository with DRY base functionality."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, ProofLake)
    
    async def create_proof(self, workspace_id: str, validator_id: str, proof_data: dict) -> ProofLake:
        """Create proof with automatic deduplication."""
        # Check for existing proof with same input hash (deduplication)
        input_hash = proof_data.get("input_hash")
        if input_hash:
            existing = await self.session.execute(
                select(ProofLake).where(
                    ProofLake.workspace_id == workspace_id,
                    ProofLake.input_hash == input_hash
                )
            )
            if existing.scalar_one_or_none():
                logger.info(f"Proof with input_hash {input_hash} already exists")
                return existing.scalar_one()
        
        proof = ProofLake(
            workspace_id=workspace_id,
            validator_id=validator_id,
            input_hash=proof_data["input_hash"],
            output_hash=proof_data["output_hash"],
            proof_data=proof_data["proof_data"],
            execution_time_ms=proof_data["execution_time_ms"],
            status=proof_data["status"]
        )
        return await self.create(proof)
    
    async def list_unsynced_proofs(self, workspace_id: str) -> list[ProofLake]:
        """List proofs that need cloud sync."""
        result = await self.session.execute(
            select(ProofLake).where(
                ProofLake.workspace_id == workspace_id,
                ProofLake.synced_to_cloud == False
            )
        )
        return result.scalars().all()


class ReplayJobRepository(BaseRepository[ReplayJob]):
    """ReplayJob repository with DRY base functionality."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, ReplayJob)
    
    async def create_replay_job(self, workspace_id: str, job_data: dict) -> ReplayJob:
        """Create replay job with validation."""
        job = ReplayJob(
            workspace_id=workspace_id,
            name=job_data["name"],
            validator_ids=job_data["validator_ids"],
            input_criteria=job_data["input_criteria"]
        )
        return await self.create(job)
    
    async def update_job_progress(self, job_id: str, completed: int, failed: int) -> ReplayJob:
        """Update job progress."""
        job = await self.get_by_id(job_id)
        if not job:
            raise ValueError(f"ReplayJob {job_id} not found")
        
        job.completed_validations = completed
        job.failed_validations = failed
        
        # Auto-complete job if all validations done
        if completed + failed >= job.total_validations:
            job.status = ReplayStatus.COMPLETED
            job.completed_at = datetime.utcnow()
        
        return await self.update(job)


# DRY: Centralized dependency injection
class DatabaseService:
    """DRY: Single service for all database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._workspace_repo = None
        self._validator_repo = None
        self._proof_repo = None
        self._replay_repo = None
    
    @property
    def workspaces(self) -> WorkspaceRepository:
        """Lazy-loaded workspace repository."""
        if self._workspace_repo is None:
            self._workspace_repo = WorkspaceRepository(self.session)
        return self._workspace_repo
    
    @property
    def validators(self) -> ValidatorRepository:
        """Lazy-loaded validator repository."""
        if self._validator_repo is None:
            self._validator_repo = ValidatorRepository(self.session)
        return self._validator_repo
    
    @property
    def proofs(self) -> ProofLakeRepository:
        """Lazy-loaded proof repository."""
        if self._proof_repo is None:
            self._proof_repo = ProofLakeRepository(self.session)
        return self._proof_repo
    
    @property
    def replay_jobs(self) -> ReplayJobRepository:
        """Lazy-loaded replay job repository."""
        if self._replay_repo is None:
            self._replay_repo = ReplayJobRepository(self.session)
        return self._replay_repo


# 12-Factor: Stateless session management
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency for FastAPI (12-Factor: stateless)."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database transaction failed: {e}")
            raise
        finally:
            await session.close()


def get_database_service(session: AsyncSession) -> DatabaseService:
    """DRY: Single database service dependency."""
    return DatabaseService(session)


# Backwards compatibility (DRY: avoid breaking existing code)
def get_workspace_repository(session: AsyncSession) -> WorkspaceRepository:
    """Workspace repository dependency (backwards compatibility)."""
    return WorkspaceRepository(session)


def get_validator_repository(session: AsyncSession) -> ValidatorRepository:
    """Validator repository dependency (backwards compatibility)."""
    return ValidatorRepository(session)


# Database lifecycle (simple and clean)
async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    await engine.dispose()


async def health_check() -> bool:
    """Database health check for 99.9% uptime SLA."""
    try:
        async with SessionLocal() as session:
            result = await session.execute(select(1))
            return result.scalar() == 1
    except Exception:
        return False
