"""
Redis Manager - Centralized Redis Connection Management

Senior Engineer Principles:
- Single responsibility: Only manages Redis connections
- Production safety: Connection pooling, retry logic, health checks
- 12-Factor: Configuration from environment
- DRY: Reusable connection patterns
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
import redis.asyncio as redis
from redis.asyncio.sentinel import Sentinel
from redis.exceptions import ConnectionError, TimeoutError, RedisError

from ..config import settings

logger = logging.getLogger(__name__)


class RedisManager:
    """
    Centralized Redis connection manager with high availability support.
    
    Features:
    - Connection pooling for performance
    - Sentinel support for high availability
    - Automatic failover and retry logic
    - Health monitoring and circuit breaker
    - Graceful degradation
    """
    
    def __init__(self):
        self._redis_pool: Optional[redis.Redis] = None
        self._sentinel: Optional[Sentinel] = None
        self._is_healthy: bool = True
        self._health_check_task: Optional[asyncio.Task] = None
        
    async def initialize(self) -> None:
        """Initialize Redis connections with production-ready configuration."""
        try:
            if settings.REDIS_SENTINEL_HOSTS:
                await self._initialize_sentinel()
            else:
                await self._initialize_single_node()
                
            # Start health monitoring
            self._health_check_task = asyncio.create_task(self._health_monitor())
            logger.info("Redis manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis manager: {e}")
            raise
    
    async def _initialize_sentinel(self) -> None:
        """Initialize Redis Sentinel for high availability."""
        sentinel_hosts = [
            (host.split(':')[0], int(host.split(':')[1])) 
            for host in settings.REDIS_SENTINEL_HOSTS.split(',')
        ]
        
        self._sentinel = Sentinel(
            sentinel_hosts,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
            retry_on_timeout=True,
            health_check_interval=30
        )
        
        # Get master connection
        self._redis_pool = self._sentinel.master_for(
            settings.REDIS_MASTER_NAME,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
            retry_on_timeout=True,
            decode_responses=True,
            max_connections=settings.REDIS_MAX_CONNECTIONS
        )
        
        logger.info(f"Redis Sentinel initialized with {len(sentinel_hosts)} sentinels")
    
    async def _initialize_single_node(self) -> None:
        """Initialize single Redis node (development/testing)."""
        self._redis_pool = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            retry_on_timeout=True,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            health_check_interval=30
        )
        
        logger.info("Redis single node initialized")
    
    async def _health_monitor(self) -> None:
        """Continuous health monitoring with circuit breaker pattern."""
        consecutive_failures = 0
        max_failures = 3
        
        while True:
            try:
                await asyncio.sleep(30)  # Health check every 30 seconds
                
                if self._redis_pool:
                    await self._redis_pool.ping()
                    
                    if consecutive_failures > 0:
                        logger.info("Redis health restored")
                        consecutive_failures = 0
                        self._is_healthy = True
                        
            except Exception as e:
                consecutive_failures += 1
                logger.warning(f"Redis health check failed ({consecutive_failures}/{max_failures}): {e}")
                
                if consecutive_failures >= max_failures:
                    self._is_healthy = False
                    logger.error("Redis marked as unhealthy - circuit breaker activated")
    
    @asynccontextmanager
    async def get_connection(self):
        """
        Get Redis connection with automatic retry and error handling.
        
        Usage:
            async with redis_manager.get_connection() as redis_conn:
                await redis_conn.set("key", "value")
        """
        if not self._is_healthy:
            raise ConnectionError("Redis is currently unhealthy")
            
        if not self._redis_pool:
            raise ConnectionError("Redis not initialized")
        
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                yield self._redis_pool
                return
                
            except (ConnectionError, TimeoutError) as e:
                if attempt == max_retries - 1:
                    logger.error(f"Redis connection failed after {max_retries} attempts: {e}")
                    raise
                    
                logger.warning(f"Redis connection attempt {attempt + 1} failed, retrying: {e}")
                await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                
            except RedisError as e:
                logger.error(f"Redis operation error: {e}")
                raise
    
    async def execute_with_retry(self, operation, *args, **kwargs) -> Any:
        """Execute Redis operation with automatic retry logic."""
        async with self.get_connection() as redis_conn:
            return await operation(redis_conn, *args, **kwargs)
    
    async def health_check(self) -> Dict[str, Any]:
        """Get detailed health status for monitoring."""
        try:
            if not self._redis_pool:
                return {"status": "unhealthy", "reason": "not_initialized"}
            
            start_time = asyncio.get_event_loop().time()
            await self._redis_pool.ping()
            latency = (asyncio.get_event_loop().time() - start_time) * 1000
            
            info = await self._redis_pool.info()
            
            return {
                "status": "healthy" if self._is_healthy else "unhealthy",
                "latency_ms": round(latency, 2),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "redis_version": info.get("redis_version", "unknown"),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0)
            }
            
        except Exception as e:
            return {
                "status": "unhealthy", 
                "reason": str(e),
                "latency_ms": None
            }
    
    async def close(self) -> None:
        """Gracefully close Redis connections."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        if self._redis_pool:
            await self._redis_pool.close()
            
        if self._sentinel:
            await self._sentinel.close()
            
        logger.info("Redis manager closed")


# Global Redis manager instance (12-Factor: Backing services as attached resources)
redis_manager = RedisManager()
