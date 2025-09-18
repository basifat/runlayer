"""
RunLayer Client

Main client class for the RunLayer SDK that manages:
- Workspace configuration and isolation
- Local ProofLake storage
- Cloud synchronization
- Authentication and API communication

RunLayer client using Repository pattern and Dependency Injection.

Following senior developer best practices:
- Repository pattern for data access abstraction
- Dependency injection for testability
- SOLID principles with proper interfaces
- 12-Factor App configuration management
"""

import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from datetime import datetime

from .models.workspace import Workspace, WorkspaceConfig
from .models.proof import RunProof
from .storage.repository import (
    DatabaseManager, 
    SQLAlchemyProofRepository, 
    SQLAlchemyWorkspaceRepository,
    IProofRepository,
    IWorkspaceRepository
)
from .storage.sync import CloudSync
from .http_client import RunLayerHTTPClient, create_http_client
from .config import get_settings
from .utils.logging import get_logger, PerformanceLogger
from .utils.crypto import KeyManager

logger = get_logger(__name__)


class RunLayerClient:
    """
    Main RunLayer SDK client using Repository pattern and Dependency Injection.
    
    Follows SOLID principles:
    - Single Responsibility: Client orchestrates operations
    - Open/Closed: Extensible via repository interfaces
    - Liskov Substitution: Repository interfaces are substitutable
    - Interface Segregation: Focused repository interfaces
    - Dependency Inversion: Depends on abstractions, not concretions
    
    Example:
        client = RunLayerClient(
            workspace="my-project",
            api_key="your-api-key",
            auto_sync=True
        )
        
        # Store a proof
        proof = RunProof.create_proof(...)
        client.store_proof(proof)
        
        # List proofs
        proofs = client.list_proofs()
    """
    
    def __init__(
        self,
        workspace: str = "default",
        storage_path: Optional[Path] = None,
        api_key: Optional[str] = None,
        auto_sync: bool = True,
        # Dependency injection for testability
        proof_repository: Optional[IProofRepository] = None,
        workspace_repository: Optional[IWorkspaceRepository] = None,
        http_client: Optional[RunLayerHTTPClient] = None,
        **config_overrides
    ):
        """
        Initialize RunLayer client with dependency injection.
        
        Args:
            workspace: Workspace name for isolation
            storage_path: Base path for local storage
            api_key: API key for cloud sync
            auto_sync: Enable automatic cloud synchronization
            proof_repository: Injected proof repository (for testing)
            workspace_repository: Injected workspace repository (for testing)
            http_client: Injected HTTP client (for testing)
            **config_overrides: Additional configuration options
        """
        self.workspace_name = workspace
        settings = get_settings()
        
        # Initialize database manager
        database_url = settings.get_database_url(workspace)
        self.db_manager = DatabaseManager(database_url)
        
        # Dependency injection - use provided repositories or create defaults
        self.proof_repository = proof_repository or SQLAlchemyProofRepository(self.db_manager)
        self.workspace_repository = workspace_repository or SQLAlchemyWorkspaceRepository(self.db_manager)
        self.http_client = http_client or create_http_client(api_key)
        
        # Load or create workspace
        base_path = Path(storage_path) if storage_path else settings.storage_path
        workspace_path = base_path / workspace
        self.workspace = self._load_or_create_workspace(
            workspace, workspace_path, api_key, auto_sync, **config_overrides
        )
        
        # Initialize key manager for signing
        self.key_manager = KeyManager(self.workspace.config.storage_path)
        
        logger.info(
            "RunLayer client initialized",
            workspace=workspace,
            storage_path=self.workspace.config.storage_path,
            auto_sync=auto_sync,
            database_url=database_url.split('://')[0] + '://***'
        )
    
    @property
    def local_storage(self):
        """Backward compatibility property for tests."""
        return self.proof_repository
    
    @property
    def _cloud_sync(self):
        """Backward compatibility property for tests."""
        return None  # Will be created lazily when needed
    
    def _load_or_create_workspace(
        self,
        name: str,
        storage_path: Path,
        api_key: Optional[str],
        auto_sync: bool,
        **config_overrides
    ) -> Workspace:
        """Load or create workspace."""
        # Try to load existing workspace
        workspace = self.workspace_repository.get_by_name(name)
        
        if workspace is None:
            # Create new workspace
            workspace = Workspace.create_workspace(
                name=name,
                storage_path=storage_path,
                api_key=api_key,
                auto_sync=auto_sync,
                **config_overrides
            )
            self.workspace_repository.create(workspace)
            logger.info("Created new workspace", workspace_id=workspace.id)
        else:
            # Update existing workspace configuration
            if api_key:
                workspace.config.api_key = api_key
            workspace.config.auto_sync = auto_sync
            
            # Update any additional config
            for key, value in config_overrides.items():
                if hasattr(workspace.config, key):
                    setattr(workspace.config, key, value)
            
            self.workspace_repository.update(workspace)
            logger.debug("Loaded existing workspace", workspace_id=workspace.id)
        
        return workspace
    
    def store_proof(self, proof: RunProof, sign: bool = True) -> bool:
        """
        Store a proof using repository pattern.
        
        Args:
            proof: The proof to store
            sign: Whether to cryptographically sign the proof
            
        Returns:
            True if stored successfully, False otherwise
        """
        with PerformanceLogger(logger, "store_proof"):
            try:
                # Sign the proof if requested
                if sign and not proof.signature:
                    private_key = self.key_manager.get_private_key()
                    signature_data = proof.get_signature_data()
                    from .utils.crypto import sign_data
                    proof.signature = sign_data(signature_data, private_key)
                
                # Store using repository pattern
                success = self.proof_repository.create(proof)
                
                if success:
                    logger.info("Proof stored successfully", proof_id=proof.id)
                    
                    # Trigger auto sync if enabled
                    if self.workspace.config.auto_sync:
                        asyncio.create_task(self._auto_sync())
                    
                    return True
                else:
                    logger.error("Failed to store proof", proof_id=proof.id)
                    return False
                    
            except Exception as e:
                logger.error("Error storing proof", proof_id=proof.id, error=str(e))
                return False
    
    def get_proof(self, proof_id: str) -> Optional[RunProof]:
        """
        Get a proof by ID.
        
        Args:
            proof_id: Proof identifier
            
        Returns:
            RunProof if found, None otherwise
        """
        return self.local_storage.get_proof(proof_id)
    
    def find_existing_proof(
        self, 
        validator_name: str, 
        validator_version: str, 
        input_hash: str
    ) -> Optional[RunProof]:
        """
        Find existing proof for the same input.
        
        Args:
            validator_name: Name of the validator
            validator_version: Version of the validator
            input_hash: Hash of the input data
            
        Returns:
            Existing RunProof if found, None otherwise
        """
        return self.local_storage.find_proof_by_input_hash(
            validator_name, validator_version, input_hash
        )
    
    def list_proofs(
        self,
        validator_name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[RunProof]:
        """
        List proofs with optional filtering.
        
        Args:
            validator_name: Filter by validator name
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of RunProofs
        """
        return self.local_storage.list_proofs(
            workspace_id=self.workspace.id,
            validator_name=validator_name,
            limit=limit,
            offset=offset
        )
    
    async def sync_to_cloud(self, force: bool = False) -> Dict[str, Any]:
        """
        Manually sync proofs to cloud.
        
        Args:
            force: Force sync even if auto_sync is disabled
            
        Returns:
            Sync results dictionary
        """
        if not self.workspace.config.api_key:
            return {
                "success": False,
                "error": "No API key configured",
                "synced_count": 0,
                "failed_count": 0
            }
        
        if not force and not self.workspace.config.auto_sync:
            return {
                "success": False,
                "error": "Auto sync is disabled",
                "synced_count": 0,
                "failed_count": 0
            }
        
        cloud_sync = await self._get_cloud_sync()
        return await cloud_sync.sync_proofs(
            batch_size=self.workspace.config.batch_sync_size
        )
    
    async def download_shared_proofs(self, validator_name: Optional[str] = None) -> List[RunProof]:
        """
        Download shared proofs from cloud.
        
        Args:
            validator_name: Optional filter by validator name
            
        Returns:
            List of downloaded proofs
        """
        if not self.workspace.config.api_key:
            logger.warning("Cannot download proofs: no API key configured")
            return []
        
        cloud_sync = await self._get_cloud_sync()
        return await cloud_sync.download_proofs(validator_name)
    
    def get_workspace_stats(self) -> Dict[str, Any]:
        """
        Get workspace statistics.
        
        Returns:
            Dictionary with workspace statistics
        """
        stats = self.local_storage.get_stats(self.workspace.id)
        sync_status = self.workspace.get_sync_status()
        
        return {
            **stats,
            **sync_status,
            "workspace_id": self.workspace.id,
            "workspace_name": self.workspace.config.name,
            "storage_path": str(self.workspace.config.storage_path),
            "created_at": self.workspace.created_at.isoformat(),
            "last_accessed": self.workspace.last_accessed.isoformat()
        }
    
    def cleanup_old_proofs(self, days: int = 30) -> int:
        """
        Clean up old proofs that have been synced.
        
        Args:
            days: Number of days to keep proofs
            
        Returns:
            Number of proofs cleaned up
        """
        return self.local_storage.cleanup_old_proofs(self.workspace.id, days)
    
    async def test_connection(self) -> bool:
        """
        Test connection to RunLayer API.
        
        Returns:
            True if connection successful
        """
        if not self.workspace.config.api_key:
            return False
        
        try:
            cloud_sync = await self._get_cloud_sync()
            return await cloud_sync.test_connection()
        except Exception as e:
            logger.error("Connection test failed", error=str(e))
            return False
    
    async def _get_cloud_sync(self) -> CloudSync:
        """Get or create CloudSync instance."""
        if self._cloud_sync is None:
            self._cloud_sync = CloudSync(
                self.workspace,
                self.local_storage,
                self.api_base_url
            )
        return self._cloud_sync
    
    async def _auto_sync(self) -> None:
        """Automatically sync proofs in background."""
        try:
            # Check if enough time has passed since last sync
            if (self.workspace.last_sync and 
                (datetime.utcnow() - self.workspace.last_sync).total_seconds() < 
                self.workspace.config.sync_interval_seconds):
                return
            
            # Perform sync
            cloud_sync = await self._get_cloud_sync()
            async with cloud_sync:
                result = await cloud_sync.sync_proofs()
                
                if result["success"]:
                    logger.debug("Auto sync completed", **result)
                else:
                    logger.warning("Auto sync failed", **result)
                    
        except Exception as e:
            logger.error("Auto sync error", error=str(e))
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        # Save workspace state
        self.workspace.save_to_path()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Close cloud sync if initialized
        if self._cloud_sync:
            await self._cloud_sync.__aexit__(exc_type, exc_val, exc_tb)
        
        # Save workspace state
        self.workspace.save_to_path()
