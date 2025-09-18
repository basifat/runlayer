"""
Redis Infrastructure Module - Story 3: Redis Cache and Job Queue

12-Factor App Compliance:
- III. Config: All Redis configuration from environment
- IV. Backing Services: Redis as attached resource
- VI. Processes: Stateless Redis operations

DRY Principles Applied:
- Single RedisManager for all Redis operations
- Reusable connection patterns
- Centralized configuration
- No code duplication across Redis clients
"""

from .manager import RedisManager, redis_manager
from .cache import CacheService, validator_cache, session_cache, result_cache
from .jobs import JobQueue, validator_queue, priority_queue, batch_queue
from .sessions import SessionManager, session_manager

__all__ = [
    "RedisManager", "redis_manager",
    "CacheService", "validator_cache", "session_cache", "result_cache",
    "JobQueue", "validator_queue", "priority_queue", "batch_queue",
    "SessionManager", "session_manager"
]
