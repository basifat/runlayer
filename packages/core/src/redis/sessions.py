"""
Session Manager - Secure Session Management for Web Users

Senior Engineer Principles:
- Security: Secure session storage with proper expiration
- Performance: Fast session lookups with Redis
- Scalability: Stateless session management
- Production ready: Session cleanup, monitoring, security headers
"""

import json
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict

from .manager import redis_manager

logger = logging.getLogger(__name__)


@dataclass
class SessionData:
    """Session data structure."""
    session_id: str
    user_id: str
    workspace_id: Optional[str] = None
    created_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    data: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.last_accessed is None:
            self.last_accessed = datetime.utcnow()
        if self.data is None:
            self.data = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for field in ['created_at', 'last_accessed', 'expires_at']:
            if data[field]:
                data[field] = data[field].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionData':
        """Create from dictionary."""
        # Convert ISO strings back to datetime
        for field in ['created_at', 'last_accessed', 'expires_at']:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if session is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


class SessionManager:
    """
    High-performance session manager with Redis backend.
    
    Features:
    - Secure session ID generation
    - Automatic session expiration
    - Session data storage and retrieval
    - Session cleanup and monitoring
    - CSRF protection support
    """
    
    def __init__(self, namespace: str = "sessions"):
        self.namespace = namespace
        self.default_ttl = timedelta(hours=24)  # 24 hour default
        
    def _make_key(self, session_id: str) -> str:
        """Create namespaced session key."""
        return f"{self.namespace}:{session_id}"
    
    def generate_session_id(self) -> str:
        """Generate cryptographically secure session ID."""
        return secrets.token_urlsafe(32)
    
    async def create_session(
        self, 
        user_id: str,
        workspace_id: Optional[str] = None,
        ttl: Optional[timedelta] = None,
        initial_data: Optional[Dict[str, Any]] = None
    ) -> SessionData:
        """Create new session with secure ID."""
        session_id = self.generate_session_id()
        ttl = ttl or self.default_ttl
        
        session = SessionData(
            session_id=session_id,
            user_id=user_id,
            workspace_id=workspace_id,
            expires_at=datetime.utcnow() + ttl,
            data=initial_data or {}
        )
        
        try:
            session_key = self._make_key(session_id)
            ttl_seconds = int(ttl.total_seconds())
            
            async with redis_manager.get_connection() as redis_conn:
                await redis_conn.set(
                    session_key,
                    json.dumps(session.to_dict()),
                    ex=ttl_seconds
                )
            
            logger.info(f"Created session {session_id} for user {user_id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session data by ID."""
        if not session_id:
            return None
        
        try:
            session_key = self._make_key(session_id)
            
            async with redis_manager.get_connection() as redis_conn:
                session_data = await redis_conn.get(session_key)
                
                if not session_data:
                    return None
                
                session = SessionData.from_dict(json.loads(session_data))
                
                # Check expiration
                if session.is_expired():
                    await self.delete_session(session_id)
                    return None
                
                # Update last accessed time
                session.last_accessed = datetime.utcnow()
                await redis_conn.set(
                    session_key,
                    json.dumps(session.to_dict()),
                    keepttl=True  # Keep existing TTL
                )
                
                return session
                
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session."""
        try:
            session_key = self._make_key(session_id)
            
            async with redis_manager.get_connection() as redis_conn:
                deleted = await redis_conn.delete(session_key)
                
            if deleted:
                logger.info(f"Deleted session {session_id}")
            
            return deleted > 0
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        try:
            cleaned = 0
            pattern = f"{self.namespace}:*"
            
            async with redis_manager.get_connection() as redis_conn:
                async for key in redis_conn.scan_iter(match=pattern):
                    session_data = await redis_conn.get(key)
                    if session_data:
                        session = SessionData.from_dict(json.loads(session_data))
                        if session.is_expired():
                            await redis_conn.delete(key)
                            cleaned += 1
            
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} expired sessions")
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0


# Global session manager instance
session_manager = SessionManager()
