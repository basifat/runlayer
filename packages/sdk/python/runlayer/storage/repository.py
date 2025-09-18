"""
Repository pattern implementation using SQLAlchemy.

Following senior developer best practices:
- Repository pattern for data access abstraction
- SQLAlchemy for ORM (industry standard)
- Dependency injection for testability
- SOLID principles with proper interfaces
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Protocol
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine, func, and_, or_
from datetime import datetime, timedelta
import logging
from contextlib import contextmanager

from .models import ProofRecord, WorkspaceRecord, Base
from ..models.proof import RunProof, ProofStatus
from ..models.workspace import Workspace, WorkspaceConfig
from ..utils.logging import get_logger

logger = get_logger(__name__)


class IProofRepository(Protocol):
    """
    Interface for proof repository operations.
    
    Follows Interface Segregation Principle (SOLID).
    """
    
    def create(self, proof: RunProof) -> bool:
        """Create a new proof record."""
        ...
    
    def get_by_id(self, proof_id: str) -> Optional[RunProof]:
        """Get proof by ID."""
        ...
    
    def find_by_input_hash(self, validator_name: str, validator_version: str, input_hash: str) -> Optional[RunProof]:
        """Find proof by input hash for caching."""
        ...
    
    def list_by_workspace(self, workspace_id: str, limit: int = 100, offset: int = 0) -> List[RunProof]:
        """List proofs by workspace."""
        ...
    
    def get_unsynced(self, workspace_id: str, limit: int = 50) -> List[RunProof]:
        """Get unsynced proofs for cloud sync."""
        ...
    
    def mark_synced(self, proof_id: str) -> bool:
        """Mark proof as synced to cloud."""
        ...
    
    def get_proof(self, proof_id: str) -> Optional[RunProof]:
        """Get proof by ID (alias for get_by_id)."""
        ...
    
    def list_proofs(self, workspace_id: str, validator_name: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[RunProof]:
        """List proofs (alias for list_by_workspace)."""
        ...
    
    def find_proof_by_input_hash(self, validator_name: str, validator_version: str, input_hash: str) -> Optional[RunProof]:
        """Find proof by input hash (alias for find_by_input_hash)."""
        ...
    
    def cleanup_old_proofs(self, workspace_id: str, days: int = 30) -> int:
        """Clean up old proofs older than specified days."""
        ...


class IWorkspaceRepository(Protocol):
    """
    Interface for workspace repository operations.
    
    Follows Interface Segregation Principle (SOLID).
    """
    
    def create(self, workspace: Workspace) -> bool:
        """Create a new workspace."""
        ...
    
    def get_by_name(self, name: str) -> Optional[Workspace]:
        """Get workspace by name."""
        ...
    
    def update(self, workspace: Workspace) -> bool:
        """Update workspace record."""
        ...
    
    def update_stats(self, workspace_id: str, total_proofs: int, synced_proofs: int, storage_mb: float) -> bool:
        """Update workspace statistics."""
        ...


class DatabaseManager:
    """
    Database connection manager using SQLAlchemy.
    
    Follows 12-Factor App principles:
    - III. Config: Database URL from environment
    - IV. Backing Services: Database as attached resource
    """
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            # Connection pool settings for production
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False  # Set to True for SQL debugging
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Create tables if they don't exist
        Base.metadata.create_all(bind=self.engine)
        
        logger.info("Database manager initialized", database_url=database_url.split('://')[0] + '://***')
    
    @contextmanager
    def get_session(self):
        """
        Get database session with proper cleanup.
        
        Uses context manager pattern for resource management.
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("Database session error", error=str(e))
            raise
        finally:
            session.close()


class SQLAlchemyProofRepository(IProofRepository):
    """
    SQLAlchemy implementation of proof repository.
    
    Follows Repository pattern with proper abstraction.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def create(self, proof: RunProof) -> bool:
        """Create a new proof record using SQLAlchemy."""
        try:
            with self.db_manager.get_session() as session:
                record = ProofRecord(
                    id=proof.id,
                    validator_name=proof.validator_name,
                    validator_version=proof.validator_version,
                    input_hash=proof.input_hash,
                    output_hash=proof.output_hash,
                    input_data=proof.input_data,
                    output_data=proof.output_data,
                    execution_time_ms=proof.execution_time_ms,
                    status=proof.status.value,
                    created_at=proof.created_at,
                    workspace_id=proof.workspace_id,
                    signature=proof.signature,
                    synced_to_cloud=proof.synced_to_cloud,
                    sync_timestamp=proof.sync_timestamp,
                    proof_metadata=proof.metadata
                )
                session.add(record)
                session.flush()  # Ensure ID is generated
                
                logger.debug("Proof created", proof_id=proof.id, validator=proof.validator_name)
                return True
                
        except Exception as e:
            # Check if it's a duplicate key error - this is actually OK
            if "UNIQUE constraint failed" in str(e) and "proofs.id" in str(e):
                logger.debug("Proof already exists", proof_id=proof.id)
                return True  # Proof already exists, which is fine
            logger.error("Failed to create proof", proof_id=proof.id, error=str(e))
            return False
    
    def get_by_id(self, proof_id: str) -> Optional[RunProof]:
        """Get proof by ID using SQLAlchemy query."""
        try:
            with self.db_manager.get_session() as session:
                record = session.query(ProofRecord).filter(ProofRecord.id == proof_id).first()
                
                if record:
                    return self._record_to_proof(record)
                return None
                
        except Exception as e:
            logger.error("Failed to get proof", proof_id=proof_id, error=str(e))
            return None
    
    def find_by_input_hash(self, validator_name: str, validator_version: str, input_hash: str) -> Optional[RunProof]:
        """Find proof by input hash for result caching."""
        try:
            with self.db_manager.get_session() as session:
                record = session.query(ProofRecord).filter(
                    and_(
                        ProofRecord.validator_name == validator_name,
                        ProofRecord.validator_version == validator_version,
                        ProofRecord.input_hash == input_hash
                    )
                ).first()
                
                if record:
                    logger.debug("Cached proof found", validator=validator_name, input_hash=input_hash[:8])
                    return self._record_to_proof(record)
                return None
                
        except Exception as e:
            logger.error("Failed to find proof by input hash", error=str(e))
            return None
    
    def list_by_workspace(self, workspace_id: str, validator_name: Optional[str] = None, 
                         limit: int = 100, offset: int = 0) -> List[RunProof]:
        """List proofs by workspace with optional filtering."""
        try:
            with self.db_manager.get_session() as session:
                query = session.query(ProofRecord).filter(ProofRecord.workspace_id == workspace_id)
                
                if validator_name:
                    query = query.filter(ProofRecord.validator_name == validator_name)
                
                records = query.order_by(ProofRecord.created_at.desc()).offset(offset).limit(limit).all()
                
                return [self._record_to_proof(record) for record in records]
                
        except Exception as e:
            logger.error("Failed to list proofs", workspace_id=workspace_id, error=str(e))
            return []
    
    def get_unsynced(self, workspace_id: str, limit: int = 50) -> List[RunProof]:
        """Get unsynced proofs for cloud synchronization."""
        try:
            with self.db_manager.get_session() as session:
                records = session.query(ProofRecord).filter(
                    and_(
                        ProofRecord.workspace_id == workspace_id,
                        ProofRecord.synced_to_cloud == False
                    )
                ).order_by(ProofRecord.created_at.asc()).limit(limit).all()
                
                return [self._record_to_proof(record) for record in records]
                
        except Exception as e:
            logger.error("Failed to get unsynced proofs", workspace_id=workspace_id, error=str(e))
            return []
    
    def mark_synced(self, proof_id: str) -> bool:
        """Mark proof as synced to cloud."""
        try:
            with self.db_manager.get_session() as session:
                updated = session.query(ProofRecord).filter(ProofRecord.id == proof_id).update({
                    ProofRecord.synced_to_cloud: True,
                    ProofRecord.sync_timestamp: datetime.utcnow()
                })
                
                if updated:
                    logger.debug("Proof marked as synced", proof_id=proof_id)
                    return True
                return False
                
        except Exception as e:
            logger.error("Failed to mark proof as synced", proof_id=proof_id, error=str(e))
            return False
    
    def get_stats(self, workspace_id: str) -> Dict[str, Any]:
        """Get workspace proof statistics."""
        try:
            with self.db_manager.get_session() as session:
                total_count = session.query(func.count(ProofRecord.id)).filter(
                    ProofRecord.workspace_id == workspace_id
                ).scalar() or 0
                
                synced_count = session.query(func.count(ProofRecord.id)).filter(
                    and_(
                        ProofRecord.workspace_id == workspace_id,
                        ProofRecord.synced_to_cloud == True
                    )
                ).scalar() or 0
                
                unique_validators = session.query(func.count(func.distinct(ProofRecord.validator_name))).filter(
                    ProofRecord.workspace_id == workspace_id
                ).scalar() or 0
                
                return {
                    "total_proofs": total_count,
                    "synced_proofs": synced_count,
                    "pending_sync": total_count - synced_count,
                    "unique_validators": unique_validators
                }
                
        except Exception as e:
            logger.error("Failed to get proof stats", workspace_id=workspace_id, error=str(e))
            return {"total_proofs": 0, "synced_proofs": 0, "pending_sync": 0, "unique_validators": 0}
    
    # Backward compatibility methods (aliases)
    def get_proof(self, proof_id: str) -> Optional[RunProof]:
        """Get proof by ID (backward compatibility alias)."""
        return self.get_by_id(proof_id)
    
    def list_proofs(self, workspace_id: str, validator_name: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[RunProof]:
        """List proofs (backward compatibility alias)."""
        return self.list_by_workspace(workspace_id, validator_name, limit, offset)
    
    def find_proof_by_input_hash(self, validator_name: str, validator_version: str, input_hash: str) -> Optional[RunProof]:
        """Find proof by input hash (backward compatibility alias)."""
        return self.find_by_input_hash(validator_name, validator_version, input_hash)
    
    def cleanup_old_proofs(self, workspace_id: str, days: int = 30) -> int:
        """Clean up old proofs older than specified days."""
        try:
            from datetime import datetime, timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            with self.db_manager.get_session() as session:
                deleted = session.query(ProofRecord).filter(
                    and_(
                        ProofRecord.workspace_id == workspace_id,
                        ProofRecord.created_at < cutoff_date
                    )
                ).delete()
                
                logger.info("Cleaned up old proofs", workspace_id=workspace_id, deleted_count=deleted, days=days)
                return deleted
                
        except Exception as e:
            logger.error("Failed to cleanup old proofs", workspace_id=workspace_id, error=str(e))
            return 0
    
    def _record_to_proof(self, record: ProofRecord) -> RunProof:
        """Convert database record to RunProof model."""
        return RunProof(
            id=record.id,
            validator_name=record.validator_name,
            validator_version=record.validator_version,
            input_hash=record.input_hash,
            output_hash=record.output_hash,
            input_data=record.input_data,
            output_data=record.output_data,
            execution_time_ms=record.execution_time_ms,
            status=ProofStatus(record.status),
            created_at=record.created_at,
            workspace_id=record.workspace_id,
            signature=record.signature,
            synced_to_cloud=record.synced_to_cloud,
            sync_timestamp=record.sync_timestamp,
            metadata=record.proof_metadata or {}
        )


class SQLAlchemyWorkspaceRepository(IWorkspaceRepository):
    """
    SQLAlchemy implementation of workspace repository.
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def create(self, workspace: Workspace) -> bool:
        """Create a new workspace record."""
        try:
            with self.db_manager.get_session() as session:
                record = WorkspaceRecord(
                    id=workspace.id,
                    name=workspace.config.name,
                    description=workspace.config.description,
                    storage_path=str(workspace.config.storage_path),
                    max_storage_mb=workspace.config.max_storage_mb,
                    auto_sync=workspace.config.auto_sync,
                    sync_interval_seconds=workspace.config.sync_interval_seconds,
                    api_base_url=workspace.config.api_base_url,
                    api_key=workspace.config.api_key,
                    max_proof_cache=workspace.config.max_proof_cache,
                    batch_sync_size=workspace.config.batch_sync_size,
                    encrypt_local_storage=workspace.config.encrypt_local_storage,
                    total_proofs=workspace.total_proofs,
                    synced_proofs=workspace.synced_proofs,
                    storage_used_mb=int(workspace.storage_used_mb),
                    is_active=workspace.is_active,
                    created_at=workspace.created_at,
                    last_accessed=workspace.last_accessed,
                    last_sync=workspace.last_sync
                )
                session.add(record)
                session.flush()
                
                logger.info("Workspace created", workspace_id=workspace.id, name=workspace.config.name)
                return True
                
        except Exception as e:
            logger.error("Failed to create workspace", workspace_name=workspace.config.name, error=str(e))
            return False
    
    def get_by_name(self, name: str) -> Optional[Workspace]:
        """Get workspace by name."""
        try:
            with self.db_manager.get_session() as session:
                record = session.query(WorkspaceRecord).filter(WorkspaceRecord.name == name).first()
                
                if record:
                    return self._record_to_workspace(record)
                return None
                
        except Exception as e:
            logger.error("Failed to get workspace", name=name, error=str(e))
            return None
    
    def update(self, workspace: Workspace) -> bool:
        """Update workspace record."""
        try:
            with self.db_manager.get_session() as session:
                updated = session.query(WorkspaceRecord).filter(WorkspaceRecord.id == workspace.id).update({
                    WorkspaceRecord.name: workspace.config.name,
                    WorkspaceRecord.description: workspace.config.description,
                    WorkspaceRecord.api_key: workspace.config.api_key,
                    WorkspaceRecord.auto_sync: workspace.config.auto_sync,
                    WorkspaceRecord.sync_interval_seconds: workspace.config.sync_interval_seconds,
                    WorkspaceRecord.max_proof_cache: workspace.config.max_proof_cache,
                    WorkspaceRecord.batch_sync_size: workspace.config.batch_sync_size,
                    WorkspaceRecord.encrypt_local_storage: workspace.config.encrypt_local_storage,
                    WorkspaceRecord.last_accessed: datetime.utcnow()
                })
                
                return updated > 0
                
        except Exception as e:
            logger.error("Failed to update workspace", workspace_id=workspace.id, error=str(e))
            return False
    
    def update_stats(self, workspace_id: str, total_proofs: int, synced_proofs: int, storage_mb: float) -> bool:
        """Update workspace statistics."""
        try:
            with self.db_manager.get_session() as session:
                updated = session.query(WorkspaceRecord).filter(WorkspaceRecord.id == workspace_id).update({
                    WorkspaceRecord.total_proofs: total_proofs,
                    WorkspaceRecord.synced_proofs: synced_proofs,
                    WorkspaceRecord.storage_used_mb: int(storage_mb),
                    WorkspaceRecord.last_accessed: datetime.utcnow()
                })
                
                return updated > 0
                
        except Exception as e:
            logger.error("Failed to update workspace stats", workspace_id=workspace_id, error=str(e))
            return False
    
    def _record_to_workspace(self, record: WorkspaceRecord) -> Workspace:
        """Convert database record to Workspace model."""
        from pathlib import Path
        
        config = WorkspaceConfig(
            name=record.name,
            description=record.description,
            storage_path=Path(record.storage_path),
            max_storage_mb=record.max_storage_mb,
            auto_sync=record.auto_sync,
            sync_interval_seconds=record.sync_interval_seconds,
            api_base_url=record.api_base_url,
            api_key=record.api_key,
            max_proof_cache=record.max_proof_cache,
            batch_sync_size=record.batch_sync_size,
            encrypt_local_storage=record.encrypt_local_storage
        )
        
        return Workspace(
            id=record.id,
            config=config,
            total_proofs=record.total_proofs,
            synced_proofs=record.synced_proofs,
            storage_used_mb=float(record.storage_used_mb),
            is_active=record.is_active,
            created_at=record.created_at,
            last_accessed=record.last_accessed,
            last_sync=record.last_sync
        )
