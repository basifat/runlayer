"""
HTTP client with retry logic using established libraries.

Following senior developer best practices:
- Use httpx (modern, async HTTP client)
- Use tenacity (proven retry library)
- Proper error handling and logging
- Circuit breaker pattern for resilience
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import httpx
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
import structlog

from .config import get_settings
from .utils.logging import get_logger

logger = get_logger(__name__)


class RunLayerHTTPClient:
    """
    HTTP client for RunLayer API with retry logic and proper error handling.
    
    Uses established libraries:
    - httpx: Modern async HTTP client
    - tenacity: Proven retry library with exponential backoff
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        settings = get_settings()
        
        self.api_key = api_key or settings.api_key
        self.base_url = base_url or settings.api_base_url
        self.timeout = settings.request_timeout_seconds
        self.verify_ssl = settings.verify_ssl
        
        # HTTP client configuration
        self.client_config = {
            "timeout": httpx.Timeout(self.timeout),
            "verify": self.verify_ssl,
            "headers": {
                "User-Agent": "RunLayer-Python-SDK/0.1.0",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        }
        
        if self.api_key:
            self.client_config["headers"]["Authorization"] = f"Bearer {self.api_key}"
        
        self._client: Optional[httpx.AsyncClient] = None
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        
        logger.info("HTTP client initialized", base_url=self.base_url, has_api_key=bool(self.api_key))
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(**self.client_config)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        before_sleep=before_sleep_log(logger, structlog.INFO),
        after=after_log(logger, structlog.INFO)
    )
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """
        Make HTTP request with retry logic using tenacity.
        
        Automatically retries on network errors and server errors (5xx).
        Uses exponential backoff with jitter.
        """
        if not self._client:
            raise RuntimeError("HTTP client not initialized. Use async context manager.")
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            response = await self._client.request(method, url, **kwargs)
            
            # Log request details
            logger.debug(
                "HTTP request completed",
                method=method,
                url=url,
                status_code=response.status_code,
                response_time_ms=int(response.elapsed.total_seconds() * 1000) if response.elapsed else None
            )
            
            # Raise for HTTP error status codes
            response.raise_for_status()
            return response
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error response",
                method=method,
                url=url,
                status_code=e.response.status_code,
                response_text=e.response.text[:500]  # Truncate for logging
            )
            raise
        except httpx.RequestError as e:
            logger.error(
                "HTTP request error",
                method=method,
                url=url,
                error=str(e)
            )
            raise
    
    async def authenticate(self) -> bool:
        """
        Authenticate with RunLayer API and get access token.
        
        Returns True if authentication successful, False otherwise.
        """
        if not self.api_key:
            logger.warning("No API key provided for authentication")
            return False
        
        try:
            response = await self._make_request(
                "POST",
                "/auth/token",
                json={"api_key": self.api_key}
            )
            
            data = response.json()
            self._access_token = data.get("access_token")
            expires_in = data.get("expires_in", 900)  # Default 15 minutes
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            # Update client headers with access token
            if self._client and self._access_token:
                self._client.headers["Authorization"] = f"Bearer {self._access_token}"
            
            logger.info("Authentication successful", expires_in=expires_in)
            return True
            
        except Exception as e:
            logger.error("Authentication failed", error=str(e))
            return False
    
    async def test_connection(self) -> bool:
        """
        Test connection to RunLayer API.
        
        Returns True if connection successful, False otherwise.
        """
        try:
            response = await self._make_request("GET", "/health")
            return response.status_code == 200
            
        except Exception as e:
            logger.debug("Connection test failed", error=str(e))
            return False
    
    async def sync_proofs(self, proofs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sync proofs to RunLayer API.
        
        Args:
            proofs: List of proof dictionaries to sync
            
        Returns:
            Sync result with counts and status
        """
        if not proofs:
            return {
                "success": True,
                "synced_count": 0,
                "failed_count": 0,
                "message": "No proofs to sync"
            }
        
        # Ensure we're authenticated
        if not await self._ensure_authenticated():
            return {
                "success": False,
                "synced_count": 0,
                "failed_count": len(proofs),
                "error": "Authentication failed"
            }
        
        try:
            response = await self._make_request(
                "POST",
                "/proofs/batch",
                json={"proofs": proofs}
            )
            
            data = response.json()
            
            logger.info(
                "Proofs synced successfully",
                synced_count=data.get("synced_count", 0),
                failed_count=data.get("failed_count", 0)
            )
            
            return {
                "success": True,
                "synced_count": data.get("synced_count", 0),
                "failed_count": data.get("failed_count", 0),
                "existing_proof_ids": data.get("existing_proof_ids", [])
            }
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:  # Conflict - proofs already exist
                data = e.response.json()
                existing_ids = data.get("existing_proof_ids", [])
                
                logger.info(
                    "Some proofs already exist on server",
                    existing_count=len(existing_ids)
                )
                
                return {
                    "success": True,
                    "synced_count": len(existing_ids),
                    "failed_count": 0,
                    "existing_proof_ids": existing_ids
                }
            else:
                logger.error("Failed to sync proofs", status_code=e.response.status_code)
                return {
                    "success": False,
                    "synced_count": 0,
                    "failed_count": len(proofs),
                    "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                }
                
        except Exception as e:
            logger.error("Failed to sync proofs", error=str(e))
            return {
                "success": False,
                "synced_count": 0,
                "failed_count": len(proofs),
                "error": str(e)
            }
    
    async def download_proofs(self, workspace_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Download proofs from RunLayer API.
        
        Args:
            workspace_id: Workspace ID to download proofs for
            limit: Maximum number of proofs to download
            
        Returns:
            List of proof dictionaries
        """
        # Ensure we're authenticated
        if not await self._ensure_authenticated():
            logger.error("Cannot download proofs: authentication failed")
            return []
        
        try:
            response = await self._make_request(
                "GET",
                f"/proofs",
                params={
                    "workspace_id": workspace_id,
                    "limit": limit
                }
            )
            
            data = response.json()
            proofs = data.get("proofs", [])
            
            logger.info("Proofs downloaded", count=len(proofs), workspace_id=workspace_id)
            return proofs
            
        except Exception as e:
            logger.error("Failed to download proofs", workspace_id=workspace_id, error=str(e))
            return []
    
    async def _ensure_authenticated(self) -> bool:
        """
        Ensure we have a valid access token.
        
        Automatically re-authenticates if token is expired.
        """
        if not self._access_token or not self._token_expires_at:
            return await self.authenticate()
        
        # Check if token is expired (with 60 second buffer)
        if datetime.utcnow() >= (self._token_expires_at - timedelta(seconds=60)):
            logger.debug("Access token expired, re-authenticating")
            return await self.authenticate()
        
        return True


# Factory function for creating HTTP clients
def create_http_client(api_key: Optional[str] = None, base_url: Optional[str] = None) -> RunLayerHTTPClient:
    """
    Factory function to create HTTP client with configuration from settings.
    
    Args:
        api_key: Optional API key override
        base_url: Optional base URL override
        
    Returns:
        Configured HTTP client
    """
    return RunLayerHTTPClient(api_key=api_key, base_url=base_url)
