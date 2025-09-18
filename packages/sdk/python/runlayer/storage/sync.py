"""
Cloud Sync for RunLayer SDK

Handles synchronization of local proofs with the RunLayer cloud API:
- Batch uploading of proofs
- Authentication and token management
- Retry logic and error handling
- Conflict resolution
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import httpx
from pathlib import Path

from ..models.proof import RunProof
from ..models.workspace import Workspace
from ..utils.logging import get_logger, PerformanceLogger, set_correlation_id
from .local import LocalProofLake

logger = get_logger(__name__)


class CloudSync:
    """
    Handles synchronization between local ProofLake and RunLayer cloud.
    
    Features:
    - Batch uploading for efficiency
    - JWT token management with refresh
    - Retry logic with exponential backoff
    - Conflict resolution strategies
    """
    
    def __init__(
        self,
        workspace: Workspace,
        local_storage: LocalProofLake,
        api_base_url: str = "https://api.runlayer.com"
    ):
        """
        Initialize CloudSync.
        
        Args:
            workspace: Workspace configuration
            local_storage: Local ProofLake instance
            api_base_url: RunLayer API base URL
        """
        self.workspace = workspace
        self.local_storage = local_storage
        self.api_base_url = api_base_url.rstrip('/')
        
        # Authentication
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        
        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.info("CloudSync initialized", 
                   workspace_id=workspace.id,
                   api_base_url=api_base_url)
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.api_base_url,
            timeout=httpx.Timeout(30.0),
            headers={
                "User-Agent": f"RunLayer-SDK/0.1.0",
                "Content-Type": "application/json"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
    
    async def authenticate(self) -> bool:
        """
        Authenticate with RunLayer API using workspace API key.
        
        Returns:
            True if authentication successful
        """
        if not self.workspace.config.api_key:
            logger.warning("No API key configured for workspace")
            return False
        
        try:
            with PerformanceLogger(logger, "authenticate"):
                response = await self._client.post("/auth/sdk-login", json={
                    "api_key": self.workspace.config.api_key,
                    "workspace_id": self.workspace.id
                })
                
                if response.status_code == 200:
                    data = response.json()
                    self._access_token = data["access_token"]
                    self._refresh_token = data.get("refresh_token")
                    
                    # Calculate token expiration (assume 15 minutes if not provided)
                    expires_in = data.get("expires_in", 900)  # 15 minutes default
                    self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                    
                    logger.info("Authentication successful")
                    return True
                else:
                    logger.error("Authentication failed", 
                               status_code=response.status_code,
                               response=response.text)
                    return False
                    
        except Exception as e:
            logger.error("Authentication error", error=str(e))
            return False
    
    async def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid access token."""
        # Check if token exists and is not expired
        if (self._access_token and self._token_expires_at and 
            datetime.utcnow() < self._token_expires_at - timedelta(minutes=1)):
            return True
        
        # Try to refresh token first
        if self._refresh_token:
            if await self._refresh_access_token():
                return True
        
        # Fall back to full authentication
        return await self.authenticate()
    
    async def _refresh_access_token(self) -> bool:
        """Refresh access token using refresh token."""
        try:
            response = await self._client.post("/auth/refresh", json={
                "refresh_token": self._refresh_token
            })
            
            if response.status_code == 200:
                data = response.json()
                self._access_token = data["access_token"]
                
                expires_in = data.get("expires_in", 900)
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                
                logger.debug("Access token refreshed")
                return True
            else:
                logger.warning("Token refresh failed", status_code=response.status_code)
                return False
                
        except Exception as e:
            logger.error("Token refresh error", error=str(e))
            return False
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        if self._access_token:
            return {"Authorization": f"Bearer {self._access_token}"}
        return {}
    
    async def sync_proofs(self, batch_size: int = 50) -> Dict[str, Any]:
        """
        Sync unsynced proofs to cloud.
        
        Args:
            batch_size: Number of proofs to sync in one batch
            
        Returns:
            Sync results dictionary
        """
        correlation_id = set_correlation_id()
        
        with PerformanceLogger(logger, "sync_proofs"):
            # Ensure authentication
            if not await self._ensure_authenticated():
                return {
                    "success": False,
                    "error": "Authentication failed",
                    "synced_count": 0,
                    "failed_count": 0
                }
            
            # Get unsynced proofs
            unsynced_proofs = self.local_storage.get_unsynced_proofs(
                self.workspace.id, 
                limit=batch_size
            )
            
            if not unsynced_proofs:
                logger.debug("No proofs to sync")
                return {
                    "success": True,
                    "synced_count": 0,
                    "failed_count": 0,
                    "message": "No proofs to sync"
                }
            
            logger.info("Starting proof sync", 
                       proof_count=len(unsynced_proofs),
                       correlation_id=correlation_id)
            
            # Sync proofs in batches
            synced_count = 0
            failed_count = 0
            
            for i in range(0, len(unsynced_proofs), batch_size):
                batch = unsynced_proofs[i:i + batch_size]
                batch_result = await self._sync_proof_batch(batch)
                
                synced_count += batch_result["synced_count"]
                failed_count += batch_result["failed_count"]
            
            # Update workspace sync timestamp
            if synced_count > 0:
                self.workspace.last_sync = datetime.utcnow()
                self.workspace.save_to_path()
            
            result = {
                "success": failed_count == 0,
                "synced_count": synced_count,
                "failed_count": failed_count,
                "correlation_id": correlation_id
            }
            
            logger.info("Proof sync completed", **result)
            return result
    
    async def _sync_proof_batch(self, proofs: List[RunProof]) -> Dict[str, Any]:
        """
        Sync a batch of proofs to cloud.
        
        Args:
            proofs: List of proofs to sync
            
        Returns:
            Batch sync results
        """
        try:
            # Prepare proof data for API
            proof_data = []
            for proof in proofs:
                proof_data.append({
                    "id": proof.id,
                    "validator_name": proof.validator_name,
                    "validator_version": proof.validator_version,
                    "input_hash": proof.input_hash,
                    "output_hash": proof.output_hash,
                    "input_data": proof.input_data,
                    "output_data": proof.output_data,
                    "execution_time_ms": proof.execution_time_ms,
                    "created_at": proof.created_at.isoformat(),
                    "signature": proof.signature,
                    "metadata": proof.metadata
                })
            
            # Send batch to API
            response = await self._client.post(
                f"/workspaces/{self.workspace.id}/proofs/batch",
                json={"proofs": proof_data},
                headers=self._get_auth_headers()
            )
            
            if response.status_code == 201:
                # Mark all proofs as synced
                synced_count = 0
                for proof in proofs:
                    if self.local_storage.mark_proof_synced(proof.id):
                        synced_count += 1
                
                logger.debug("Batch sync successful", 
                           batch_size=len(proofs),
                           synced_count=synced_count)
                
                return {
                    "synced_count": synced_count,
                    "failed_count": len(proofs) - synced_count
                }
            
            elif response.status_code == 409:
                # Handle conflicts (some proofs already exist)
                response_data = response.json()
                existing_ids = set(response_data.get("existing_proof_ids", []))
                
                synced_count = 0
                for proof in proofs:
                    if proof.id in existing_ids:
                        # Mark as synced since it already exists in cloud
                        if self.local_storage.mark_proof_synced(proof.id):
                            synced_count += 1
                
                logger.info("Batch sync with conflicts resolved",
                           total_proofs=len(proofs),
                           existing_proofs=len(existing_ids),
                           synced_count=synced_count)
                
                return {
                    "synced_count": synced_count,
                    "failed_count": len(proofs) - synced_count
                }
            
            else:
                logger.error("Batch sync failed",
                           status_code=response.status_code,
                           response=response.text)
                
                return {
                    "synced_count": 0,
                    "failed_count": len(proofs)
                }
                
        except Exception as e:
            logger.error("Batch sync error", error=str(e))
            return {
                "synced_count": 0,
                "failed_count": len(proofs)
            }
    
    async def download_proofs(self, validator_name: Optional[str] = None) -> List[RunProof]:
        """
        Download proofs from cloud (for sharing/collaboration).
        
        Args:
            validator_name: Optional filter by validator name
            
        Returns:
            List of downloaded proofs
        """
        if not await self._ensure_authenticated():
            logger.error("Cannot download proofs: authentication failed")
            return []
        
        try:
            params = {}
            if validator_name:
                params["validator_name"] = validator_name
            
            response = await self._client.get(
                f"/workspaces/{self.workspace.id}/proofs",
                params=params,
                headers=self._get_auth_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                proofs = []
                
                for proof_data in data.get("proofs", []):
                    try:
                        proof = RunProof(**proof_data)
                        proofs.append(proof)
                    except Exception as e:
                        logger.warning("Failed to parse proof", error=str(e))
                
                logger.info("Downloaded proofs from cloud", count=len(proofs))
                return proofs
            
            else:
                logger.error("Failed to download proofs",
                           status_code=response.status_code)
                return []
                
        except Exception as e:
            logger.error("Download proofs error", error=str(e))
            return []
    
    async def test_connection(self) -> bool:
        """
        Test connection to RunLayer API.
        
        Returns:
            True if connection successful
        """
        try:
            response = await self._client.get("/health")
            return response.status_code == 200
        except Exception as e:
            logger.error("Connection test failed", error=str(e))
            return False
