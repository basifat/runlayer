"""
Workspace Model

Represents a RunLayer workspace for project isolation.
Each workspace has its own:
- Local ProofLake storage
- Configuration settings
- Sync preferences
- Quota limits
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import os


class WorkspaceConfig(BaseModel):
    """Configuration for a RunLayer workspace."""
    
    # Basic settings
    name: str = Field(..., description="Workspace name")
    description: Optional[str] = Field(None, description="Workspace description")
    
    # Storage settings
    storage_path: Path = Field(..., description="Local storage directory path")
    max_storage_mb: int = Field(default=100, description="Maximum storage in MB")
    
    # Sync settings
    auto_sync: bool = Field(default=True, description="Automatically sync to cloud")
    sync_interval_seconds: int = Field(default=300, description="Sync interval in seconds")
    
    # API settings
    api_base_url: str = Field(default="https://api.runlayer.com", description="RunLayer API base URL")
    api_key: Optional[str] = Field(None, description="API key for cloud sync")
    
    # Performance settings
    max_proof_cache: int = Field(default=1000, description="Maximum proofs to cache in memory")
    batch_sync_size: int = Field(default=50, description="Number of proofs to sync in one batch")
    
    # Security settings
    encrypt_local_storage: bool = Field(default=True, description="Encrypt local SQLite database")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            Path: str,
        }


class Workspace(BaseModel):
    """
    A RunLayer workspace for project isolation.
    
    Each workspace maintains its own local ProofLake and configuration,
    allowing multiple projects to use RunLayer independently.
    """
    
    # Identity
    id: str = Field(..., description="Unique workspace identifier")
    config: WorkspaceConfig = Field(..., description="Workspace configuration")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    last_accessed: datetime = Field(default_factory=datetime.utcnow, description="Last access timestamp")
    
    # Statistics
    total_proofs: int = Field(default=0, description="Total number of proofs")
    synced_proofs: int = Field(default=0, description="Number of synced proofs")
    storage_used_mb: float = Field(default=0.0, description="Storage used in MB")
    
    # Status
    is_active: bool = Field(default=True, description="Whether workspace is active")
    last_sync: Optional[datetime] = Field(None, description="Last successful sync timestamp")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Path: str,
        }
    
    @classmethod
    def create_workspace(
        cls,
        name: str,
        storage_path: Optional[Path] = None,
        api_key: Optional[str] = None,
        **config_kwargs
    ) -> "Workspace":
        """
        Create a new workspace with default configuration.
        
        Args:
            name: Workspace name
            storage_path: Custom storage path (defaults to ~/.runlayer/{name})
            api_key: API key for cloud sync
            **config_kwargs: Additional configuration options
            
        Returns:
            New Workspace instance
        """
        # Generate workspace ID
        import hashlib
        workspace_id = hashlib.sha256(f"{name}:{datetime.utcnow().isoformat()}".encode()).hexdigest()[:16]
        
        # Set default storage path
        if storage_path is None:
            home_dir = Path.home()
            storage_path = home_dir / ".runlayer" / name
        
        # Create storage directory
        storage_path.mkdir(parents=True, exist_ok=True)
        
        # Create configuration
        config = WorkspaceConfig(
            name=name,
            storage_path=storage_path,
            api_key=api_key,
            **config_kwargs
        )
        
        return cls(
            id=workspace_id,
            config=config
        )
    
    @classmethod
    def load_from_path(cls, storage_path: Path) -> Optional["Workspace"]:
        """
        Load workspace from storage path.
        
        Args:
            storage_path: Path to workspace storage directory
            
        Returns:
            Workspace instance if found, None otherwise
        """
        config_file = storage_path / "workspace.json"
        if not config_file.exists():
            return None
        
        try:
            import json
            with open(config_file, 'r') as f:
                data = json.load(f)
            return cls.parse_obj(data)
        except Exception:
            return None
    
    def save_to_path(self) -> None:
        """Save workspace configuration to storage path."""
        config_file = self.config.storage_path / "workspace.json"
        
        # Ensure directory exists
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Save configuration
        import json
        with open(config_file, 'w') as f:
            json.dump(self.dict(), f, indent=2, default=str)
    
    def get_database_path(self) -> Path:
        """Get path to local ProofLake database."""
        return self.config.storage_path / "prooflake.db"
    
    def update_access_time(self) -> None:
        """Update last accessed timestamp."""
        self.last_accessed = datetime.utcnow()
    
    def update_stats(self, total_proofs: int, synced_proofs: int, storage_mb: float) -> None:
        """
        Update workspace statistics.
        
        Args:
            total_proofs: Total number of proofs
            synced_proofs: Number of synced proofs
            storage_mb: Storage used in MB
        """
        self.total_proofs = total_proofs
        self.synced_proofs = synced_proofs
        self.storage_used_mb = storage_mb
    
    def is_over_quota(self) -> bool:
        """Check if workspace is over storage quota."""
        return self.storage_used_mb > self.config.max_storage_mb
    
    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get sync status information.
        
        Returns:
            Dictionary with sync status details
        """
        return {
            "total_proofs": self.total_proofs,
            "synced_proofs": self.synced_proofs,
            "pending_sync": self.total_proofs - self.synced_proofs,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "auto_sync_enabled": self.config.auto_sync,
            "has_api_key": bool(self.config.api_key)
        }
    
    def cleanup_old_proofs(self, days: int = 30) -> int:
        """
        Clean up proofs older than specified days.
        
        Args:
            days: Number of days to keep proofs
            
        Returns:
            Number of proofs cleaned up
        """
        # This would be implemented with the LocalProofLake
        # For now, return 0 as placeholder
        return 0
