"""
Cache Service - High-Performance Caching Layer

Senior Engineer Principles:
- Performance: <10ms cache hit latency requirement
- Type safety: Generic caching with proper serialization
- Production ready: TTL management, cache warming, metrics
- DRY: Reusable caching patterns
"""

import json
import pickle
import logging
from typing import Any, Optional, Union, Dict, List, TypeVar, Generic
from datetime import timedelta
import asyncio
from dataclasses import dataclass

from .manager import redis_manager

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheMetrics:
    """Cache performance metrics for monitoring."""
    hits: int = 0
    misses: int = 0
    errors: int = 0
    total_requests: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.hits / self.total_requests) * 100


class CacheService(Generic[T]):
    """
    High-performance caching service with production features.
    
    Features:
    - Generic type support for type safety
    - Multiple serialization strategies (JSON, Pickle)
    - TTL management with automatic expiration
    - Cache warming and preloading
    - Performance metrics and monitoring
    - Batch operations for efficiency
    """
    
    def __init__(self, namespace: str = "cache"):
        self.namespace = namespace
        self.metrics = CacheMetrics()
        
    def _make_key(self, key: str) -> str:
        """Create namespaced cache key."""
        return f"{self.namespace}:{key}"
    
    async def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """
        Get value from cache with automatic deserialization.
        
        Performance target: <10ms for cache hits
        """
        cache_key = self._make_key(key)
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            async with redis_manager.get_connection() as redis_conn:
                # Try JSON first (faster), then pickle
                json_value = await redis_conn.get(f"{cache_key}:json")
                if json_value:
                    result = json.loads(json_value)
                    self._record_hit(start_time)
                    return result
                
                # Try pickle for complex objects
                pickle_value = await redis_conn.get(f"{cache_key}:pickle")
                if pickle_value:
                    result = pickle.loads(pickle_value)
                    self._record_hit(start_time)
                    return result
            
            self._record_miss()
            return default
            
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self.metrics.errors += 1
            return default
    
    async def set(
        self, 
        key: str, 
        value: T, 
        ttl: Optional[Union[int, timedelta]] = None,
        use_pickle: bool = False
    ) -> bool:
        """
        Set value in cache with automatic serialization.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live (seconds or timedelta)
            use_pickle: Use pickle for complex objects
        """
        cache_key = self._make_key(key)
        
        try:
            # Convert TTL to seconds
            ttl_seconds = None
            if ttl:
                if isinstance(ttl, timedelta):
                    ttl_seconds = int(ttl.total_seconds())
                else:
                    ttl_seconds = ttl
            
            async with redis_manager.get_connection() as redis_conn:
                if use_pickle:
                    # Use pickle for complex objects
                    serialized = pickle.dumps(value)
                    await redis_conn.set(f"{cache_key}:pickle", serialized, ex=ttl_seconds)
                else:
                    # Try JSON first (faster and more readable)
                    try:
                        serialized = json.dumps(value, default=str)
                        await redis_conn.set(f"{cache_key}:json", serialized, ex=ttl_seconds)
                    except (TypeError, ValueError):
                        # Fallback to pickle for non-JSON serializable objects
                        serialized = pickle.dumps(value)
                        await redis_conn.set(f"{cache_key}:pickle", serialized, ex=ttl_seconds)
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            self.metrics.errors += 1
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        cache_key = self._make_key(key)
        
        try:
            async with redis_manager.get_connection() as redis_conn:
                # Delete both JSON and pickle versions
                deleted = await redis_conn.delete(
                    f"{cache_key}:json",
                    f"{cache_key}:pickle"
                )
                return deleted > 0
                
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            self.metrics.errors += 1
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        cache_key = self._make_key(key)
        
        try:
            async with redis_manager.get_connection() as redis_conn:
                exists = await redis_conn.exists(
                    f"{cache_key}:json",
                    f"{cache_key}:pickle"
                )
                return exists > 0
                
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    async def get_many(self, keys: List[str]) -> Dict[str, Optional[T]]:
        """Batch get operation for efficiency."""
        if not keys:
            return {}
        
        result = {}
        
        try:
            # Build all cache keys
            json_keys = [f"{self._make_key(key)}:json" for key in keys]
            pickle_keys = [f"{self._make_key(key)}:pickle" for key in keys]
            
            async with redis_manager.get_connection() as redis_conn:
                # Get all JSON values
                json_values = await redis_conn.mget(json_keys)
                
                # Get all pickle values
                pickle_values = await redis_conn.mget(pickle_keys)
                
                # Process results
                for i, key in enumerate(keys):
                    if json_values[i]:
                        result[key] = json.loads(json_values[i])
                        self.metrics.hits += 1
                    elif pickle_values[i]:
                        result[key] = pickle.loads(pickle_values[i])
                        self.metrics.hits += 1
                    else:
                        result[key] = None
                        self.metrics.misses += 1
                    
                    self.metrics.total_requests += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Cache get_many error: {e}")
            self.metrics.errors += len(keys)
            return {key: None for key in keys}
    
    async def set_many(
        self, 
        items: Dict[str, T], 
        ttl: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Batch set operation for efficiency."""
        if not items:
            return True
        
        try:
            # Convert TTL to seconds
            ttl_seconds = None
            if ttl:
                if isinstance(ttl, timedelta):
                    ttl_seconds = int(ttl.total_seconds())
                else:
                    ttl_seconds = ttl
            
            async with redis_manager.get_connection() as redis_conn:
                # Use pipeline for batch operations
                pipe = redis_conn.pipeline()
                
                for key, value in items.items():
                    cache_key = self._make_key(key)
                    
                    try:
                        # Try JSON first
                        serialized = json.dumps(value, default=str)
                        pipe.set(f"{cache_key}:json", serialized, ex=ttl_seconds)
                    except (TypeError, ValueError):
                        # Fallback to pickle
                        serialized = pickle.dumps(value)
                        pipe.set(f"{cache_key}:pickle", serialized, ex=ttl_seconds)
                
                await pipe.execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set_many error: {e}")
            self.metrics.errors += len(items)
            return False
    
    async def clear_namespace(self) -> int:
        """Clear all keys in this namespace."""
        try:
            async with redis_manager.get_connection() as redis_conn:
                pattern = f"{self.namespace}:*"
                keys = []
                
                async for key in redis_conn.scan_iter(match=pattern):
                    keys.append(key)
                
                if keys:
                    deleted = await redis_conn.delete(*keys)
                    logger.info(f"Cleared {deleted} keys from namespace {self.namespace}")
                    return deleted
                
                return 0
                
        except Exception as e:
            logger.error(f"Cache clear_namespace error: {e}")
            return 0
    
    def _record_hit(self, start_time: float) -> None:
        """Record cache hit with latency tracking."""
        latency = (asyncio.get_event_loop().time() - start_time) * 1000
        self.metrics.hits += 1
        self.metrics.total_requests += 1
        
        # Log slow cache hits (>10ms target)
        if latency > 10:
            logger.warning(f"Slow cache hit: {latency:.2f}ms")
    
    def _record_miss(self) -> None:
        """Record cache miss."""
        self.metrics.misses += 1
        self.metrics.total_requests += 1
    
    def get_metrics(self) -> CacheMetrics:
        """Get current cache metrics."""
        return self.metrics
    
    def reset_metrics(self) -> None:
        """Reset cache metrics."""
        self.metrics = CacheMetrics()


# Pre-configured cache services for common use cases
validator_cache = CacheService[Dict[str, Any]]("validators")
session_cache = CacheService[Dict[str, Any]]("sessions")
result_cache = CacheService[Dict[str, Any]]("results")
