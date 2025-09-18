"""
SQLAlchemy models for RunLayer SDK - Using established ORM instead of raw SQL.

Following senior developer best practices:
- Use SQLAlchemy (industry standard ORM)
- Proper database schema with migrations
- Type-safe database operations
- Connection pooling and optimization
"""

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from typing import Dict, Any

Base = declarative_base()


class ProofRecord(Base):
    """
    SQLAlchemy model for RunProof storage.
    
    Uses established ORM patterns instead of raw SQL.
    Follows database best practices with proper indexing.
    """
    __tablename__ = 'proofs'
    
    # Primary key
    id = Column(String(16), primary_key=True)
    
    # Validator information
    validator_name = Column(String(255), nullable=False, index=True)
    validator_version = Column(String(50), nullable=False)
    
    # Integrity hashes
    input_hash = Column(String(64), nullable=False, index=True)
    output_hash = Column(String(64), nullable=False)
    
    # Data (stored as JSON)
    input_data = Column(JSON, nullable=False)
    output_data = Column(JSON, nullable=False)
    
    # Execution metadata
    execution_time_ms = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default='created', index=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    # Workspace isolation
    workspace_id = Column(String(16), nullable=False, index=True)
    
    # Cryptographic signature
    signature = Column(Text, nullable=True)
    
    # Sync tracking
    synced_to_cloud = Column(Boolean, nullable=False, default=False, index=True)
    sync_timestamp = Column(DateTime, nullable=True)
    
    # Additional metadata
    metadata = Column(JSON, nullable=False, default=dict)
    
    # Composite indexes for performance
    __table_args__ = (
        Index('idx_validator_workspace', 'validator_name', 'workspace_id'),
        Index('idx_input_hash_validator', 'input_hash', 'validator_name', 'validator_version'),
        Index('idx_workspace_status', 'workspace_id', 'status'),
        Index('idx_workspace_sync', 'workspace_id', 'synced_to_cloud'),
        Index('idx_created_workspace', 'created_at', 'workspace_id'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization."""
        return {
            'id': self.id,
            'validator_name': self.validator_name,
            'validator_version': self.validator_version,
            'input_hash': self.input_hash,
            'output_hash': self.output_hash,
            'input_data': self.input_data,
            'output_data': self.output_data,
            'execution_time_ms': self.execution_time_ms,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'workspace_id': self.workspace_id,
            'signature': self.signature,
            'synced_to_cloud': self.synced_to_cloud,
            'sync_timestamp': self.sync_timestamp.isoformat() if self.sync_timestamp else None,
            'metadata': self.metadata or {}
        }


class WorkspaceRecord(Base):
    """
    SQLAlchemy model for Workspace storage.
    
    Stores workspace configuration and statistics.
    """
    __tablename__ = 'workspaces'
    
    # Primary key
    id = Column(String(16), primary_key=True)
    
    # Configuration
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    
    # Storage settings
    storage_path = Column(String(500), nullable=False)
    max_storage_mb = Column(Integer, nullable=False, default=100)
    
    # Sync settings
    auto_sync = Column(Boolean, nullable=False, default=True)
    sync_interval_seconds = Column(Integer, nullable=False, default=300)
    
    # API settings
    api_base_url = Column(String(500), nullable=False, default="https://api.runlayer.com")
    api_key = Column(String(500), nullable=True)  # Encrypted in production
    
    # Performance settings
    max_proof_cache = Column(Integer, nullable=False, default=1000)
    batch_sync_size = Column(Integer, nullable=False, default=50)
    
    # Security settings
    encrypt_local_storage = Column(Boolean, nullable=False, default=True)
    
    # Statistics
    total_proofs = Column(Integer, nullable=False, default=0)
    synced_proofs = Column(Integer, nullable=False, default=0)
    storage_used_mb = Column(Integer, nullable=False, default=0)
    
    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    last_accessed = Column(DateTime, nullable=False, default=func.now())
    last_sync = Column(DateTime, nullable=True)
    
    # Additional configuration
    config_json = Column(JSON, nullable=False, default=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'storage_path': self.storage_path,
            'max_storage_mb': self.max_storage_mb,
            'auto_sync': self.auto_sync,
            'sync_interval_seconds': self.sync_interval_seconds,
            'api_base_url': self.api_base_url,
            'has_api_key': bool(self.api_key),  # Don't expose actual key
            'max_proof_cache': self.max_proof_cache,
            'batch_sync_size': self.batch_sync_size,
            'encrypt_local_storage': self.encrypt_local_storage,
            'total_proofs': self.total_proofs,
            'synced_proofs': self.synced_proofs,
            'storage_used_mb': self.storage_used_mb,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'config': self.config_json or {}
        }
