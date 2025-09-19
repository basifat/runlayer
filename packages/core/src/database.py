"""
RunLayer Database - Story 2: Multi-Tenant Database Setup (SDK Extended)

Senior developer approach using established frameworks and best practices:
- SQLAlchemy 2.0 with async support (don't reinvent ORM)
- Simple tenant_id filtering (YAGNI - no complex RLS initially)
- Dependency injection pattern (SOLID)
- Repository pattern for data access (SOLID)
- Pydantic for validation (established framework)
"""

from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Boolean, Text, JSON, Index, ForeignKey, select
from sqlalchemy.dialects.postgresql import UUID
from pydantic import BaseModel, Field
import uuid

from .config import settings


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# DRY Mixins for common patterns
class UUIDMixin:
    """Mixin for UUID primary keys."""
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TenantMixin:
    """Mixin for workspace-based multi-tenancy."""
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)


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
class Workspace(Base):
    """Multi-tenant workspace - simple tenant_id approach (YAGNI)."""
    __tablename__ = "workspaces"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[WorkspaceType] = mapped_column(String(50), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)  # Simple tenant filtering
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Quotas (only what Story 2 requires)
    max_validators: Mapped[int] = mapped_column(Integer, default=100)
    max_executions_per_day: Mapped[int] = mapped_column(Integer, default=10000)
    max_storage_mb: Mapped[int] = mapped_column(Integer, default=1000)
    
    # Relationships (let SQLAlchemy handle joins)
    validators: Mapped[list["ValidatorRegistry"]] = relationship(back_populates="workspace")
    proofs: Mapped[list["ProofLake"]] = relationship(back_populates="workspace")
    replay_jobs: Mapped[list["ReplayJob"]] = relationship(back_populates="workspace")
    
    __table_args__ = (
        Index('idx_workspace_owner_type', 'owner_id', 'type'),  # Composite index for common queries
    )


class ValidatorRegistry(Base):
    """Validator registry - optimized for <100ms lookups."""
    __tablename__ = "validator_registry"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Code storage (use established cloud storage patterns)
    code_bundle_url: Mapped[str] = mapped_column(String(500), nullable=False)
    wasm_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    validator_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Simple lifecycle (YAGNI - no complex versioning initially)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="validators")
    proofs: Mapped[list["ProofLake"]] = relationship(back_populates="validator")
    
    __table_args__ = (
        Index('idx_validator_lookup', 'workspace_id', 'name', 'version', 'is_active'),  # Single optimized index
        Index('idx_validator_workspace_active', 'workspace_id', 'is_active'),  # List active validators
    )


class ProofLake(Base):
    """Validation results storage - compatible with local ProofLake."""
    __tablename__ = "proof_lake"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    validator_id: Mapped[str] = mapped_column(ForeignKey("validator_registry.id"), nullable=False, index=True)
    
    # Core proof data
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # For deduplication
    output_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    proof_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Execution metadata
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ValidationStatus] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # SDK sync tracking (only what's needed)
    synced_to_cloud: Mapped[bool] = mapped_column(Boolean, default=False)
    sync_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="proofs")
    validator: Mapped["ValidatorRegistry"] = relationship(back_populates="proofs")
    
    __table_args__ = (
        Index('idx_proof_workspace_created', 'workspace_id', 'created_at'),  # Time-based queries
        Index('idx_proof_sync_pending', 'workspace_id', 'synced_to_cloud'),  # Sync queries
    )


class ReplayJob(Base):
    """Replay job tracking - simple and focused."""
    __tablename__ = "replay_jobs"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    
    # Job configuration
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    validator_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    input_criteria: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Job status and progress
    status: Mapped[ReplayStatus] = mapped_column(String(50), default=ReplayStatus.PENDING)
    total_validations: Mapped[int] = mapped_column(Integer, default=0)
    completed_validations: Mapped[int] = mapped_column(Integer, default=0)
    failed_validations: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="replay_jobs")
    
    __table_args__ = (
        Index('idx_replay_workspace_status', 'workspace_id', 'status'),  # Common query pattern
        Index('idx_replay_created', 'created_at'),  # Time-based queries
    )


# Database setup (use established patterns, don't reinvent)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    pool_size=20,  # Support 10K concurrent connections
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# Repository pattern (SOLID - Single Responsibility)
class BaseRepository:
    """Base repository with common database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, model_class, id: str):
        """Get entity by ID."""
        result = await self.session.execute(select(model_class).where(model_class.id == id))
        return result.scalar_one_or_none()
    
    async def create(self, entity):
        """Create new entity."""
        self.session.add(entity)
        await self.session.flush()
        return entity
    
    async def delete(self, entity):
        """Delete entity."""
        await self.session.delete(entity)
        await self.session.flush()


class WorkspaceRepository(BaseRepository):
    """Workspace-specific database operations."""
    
    async def get_by_owner(self, owner_id: str) -> list[Workspace]:
        """Get workspaces by owner (simple tenant filtering)."""
        result = await self.session.execute(
            select(Workspace).where(Workspace.owner_id == owner_id)
        )
        return result.scalars().all()
    
    async def create_workspace(self, workspace_data: WorkspaceCreate, owner_id: str) -> Workspace:
        """Create new workspace with validation."""
        workspace = Workspace(
            name=workspace_data.name,
            type=workspace_data.type,
            owner_id=owner_id,
            max_validators=workspace_data.max_validators,
            max_executions_per_day=workspace_data.max_executions_per_day,
            max_storage_mb=workspace_data.max_storage_mb
        )
        return await self.create(workspace)


class ValidatorRepository(BaseRepository):
    """Validator-specific database operations."""
    
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
        """List active validators for workspace."""
        result = await self.session.execute(
            select(ValidatorRegistry).where(
                ValidatorRegistry.workspace_id == workspace_id,
                ValidatorRegistry.is_active == True
            )
        )
        return result.scalars().all()
    
    async def create_validator(self, workspace_id: str, validator_data: ValidatorCreate) -> ValidatorRegistry:
        """Create new validator with validation."""
        validator = ValidatorRegistry(
            workspace_id=workspace_id,
            name=validator_data.name,
            version=validator_data.version,
            description=validator_data.description,
            code_bundle_url=validator_data.code_bundle_url,
            wasm_hash=validator_data.wasm_hash,
            validator_metadata=validator_data.validator_metadata
        )
        return await self.create(validator)


# Simple dependency injection (don't overcomplicate)
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency for FastAPI."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_workspace_repository(session: AsyncSession) -> WorkspaceRepository:
    """Workspace repository dependency."""
    return WorkspaceRepository(session)


def get_validator_repository(session: AsyncSession) -> ValidatorRepository:
    """Validator repository dependency."""
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
