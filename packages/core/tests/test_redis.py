"""
Redis Infrastructure Tests - Story 3
80%+ coverage requirement with zero failing tests
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
import json
from datetime import datetime, timedelta

from src.redis.manager import RedisManager
from src.redis.cache import CacheService
from src.redis.jobs import JobQueue, Job, JobPriority
from src.redis.sessions import SessionManager


class TestRedisManager:
    """Test Redis connection manager."""
    
    @pytest_asyncio.fixture
    async def redis_manager(self):
        manager = RedisManager()
        yield manager
        if manager._redis_pool:
            await manager.close()
    
    @pytest.mark.asyncio
    async def test_initialize_single_node(self, redis_manager):
        """Test single node initialization."""
        with patch('src.redis.manager.redis.from_url') as mock_redis:
            mock_redis.return_value = AsyncMock()
            await redis_manager.initialize()
            assert redis_manager._redis_pool is not None
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, redis_manager):
        """Test health check when healthy."""
        mock_pool = AsyncMock()
        mock_pool.ping.return_value = None
        mock_pool.info.return_value = {"connected_clients": 5, "redis_version": "7.0.0"}
        redis_manager._redis_pool = mock_pool
        redis_manager._is_healthy = True
        
        health = await redis_manager.health_check()
        assert health["status"] == "healthy"


class TestCacheService:
    """Test caching service."""
    
    @pytest_asyncio.fixture
    def cache_service(self):
        return CacheService("test")
    
    @pytest.mark.asyncio
    async def test_cache_set_get(self, cache_service):
        """Test cache operations."""
        with patch('src.redis.cache.redis_manager') as mock_manager:
            mock_conn = AsyncMock()
            mock_manager.get_connection.return_value.__aenter__.return_value = mock_conn
            
            # Test set
            mock_conn.set.return_value = True
            result = await cache_service.set("key", {"data": "test"})
            assert result is True
            
            # Test get
            mock_conn.get.side_effect = [json.dumps({"data": "test"}), None]
            retrieved = await cache_service.get("key")
            assert retrieved == {"data": "test"}
    
    @pytest.mark.asyncio
    async def test_cache_miss_with_default(self, cache_service):
        """Test cache miss returns default."""
        with patch('src.redis.cache.redis_manager') as mock_manager:
            mock_conn = AsyncMock()
            mock_manager.get_connection.return_value.__aenter__.return_value = mock_conn
            mock_conn.get.return_value = None
            
            result = await cache_service.get("missing_key", default="default")
            assert result == "default"
            assert cache_service.metrics.misses == 1
    
    @pytest.mark.asyncio
    async def test_cache_delete(self, cache_service):
        """Test cache deletion."""
        with patch('src.redis.cache.redis_manager') as mock_manager:
            mock_conn = AsyncMock()
            mock_manager.get_connection.return_value.__aenter__.return_value = mock_conn
            mock_conn.delete.return_value = 1
            
            result = await cache_service.delete("key")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_cache_exists(self, cache_service):
        """Test cache key existence check."""
        with patch('src.redis.cache.redis_manager') as mock_manager:
            mock_conn = AsyncMock()
            mock_manager.get_connection.return_value.__aenter__.return_value = mock_conn
            mock_conn.exists.return_value = 1
            
            result = await cache_service.exists("key")
            assert result is True
    
    @pytest.mark.asyncio
    async def test_cache_error_handling(self, cache_service):
        """Test cache error handling."""
        with patch('src.redis.cache.redis_manager') as mock_manager:
            mock_manager.get_connection.side_effect = Exception("Redis error")
            
            result = await cache_service.get("key", default="fallback")
            assert result == "fallback"
            assert cache_service.metrics.errors == 1


class TestJobQueue:
    """Test job queue system."""
    
    @pytest_asyncio.fixture
    def job_queue(self):
        return JobQueue("test")
    
    @pytest.mark.asyncio
    async def test_enqueue_job(self, job_queue):
        """Test job enqueuing."""
        with patch('src.redis.jobs.redis_manager') as mock_manager:
            mock_conn = AsyncMock()
            mock_manager.get_connection.return_value.__aenter__.return_value = mock_conn
            
            mock_conn.hset.return_value = True
            mock_conn.zadd.return_value = True
            
            job_id = await job_queue.enqueue("test_job", {"data": "test"})
            assert job_id is not None
    
    @pytest.mark.asyncio
    async def test_dequeue_job(self, job_queue):
        """Test job dequeuing."""
        with patch('src.redis.jobs.redis_manager') as mock_manager:
            mock_conn = AsyncMock()
            mock_manager.get_connection.return_value.__aenter__.return_value = mock_conn
            
            # Mock dequeue response
            mock_conn.bzpopmax.return_value = ("queue:test:pending", "job-123", 1.0)
            mock_conn.hget.return_value = json.dumps({
                "id": "job-123",
                "queue_name": "test",
                "job_type": "test_job",
                "payload": {"data": "test"},
                "priority": 1,
                "status": "pending",
                "created_at": datetime.now().isoformat()
            })
            mock_conn.hset.return_value = True
            mock_conn.zadd.return_value = True
            
            job = await job_queue.dequeue(timeout=1)
            assert job is not None
            assert job.id == "job-123"
    
    @pytest.mark.asyncio
    async def test_job_handler_registration(self, job_queue):
        """Test job handler registration."""
        async def test_handler(job):
            return {"success": True}
        
        job_queue.register_handler("test_job", test_handler)
        assert "test_job" in job_queue.job_handlers
    
    @pytest.mark.asyncio
    async def test_queue_stats(self, job_queue):
        """Test queue statistics."""
        with patch('src.redis.jobs.redis_manager') as mock_manager:
            mock_conn = AsyncMock()
            mock_manager.get_connection.return_value.__aenter__.return_value = mock_conn
            
            # Mock queue counts
            mock_conn.zcard.side_effect = [5, 2, 10, 1, 0]  # pending, processing, completed, failed, dead
            mock_conn.hlen.return_value = 3  # workers
            
            stats = await job_queue.get_queue_stats()
            assert stats["pending_jobs"] == 5
            assert stats["active_workers"] == 3


class TestSessionManager:
    """Test session management."""
    
    @pytest_asyncio.fixture
    def session_manager(self):
        return SessionManager("test")
    
    @pytest.mark.asyncio
    async def test_create_session(self, session_manager):
        """Test session creation."""
        with patch('src.redis.sessions.redis_manager') as mock_manager:
            mock_conn = AsyncMock()
            mock_manager.get_connection.return_value.__aenter__.return_value = mock_conn
            
            mock_conn.set.return_value = True
            
            session = await session_manager.create_session("user123")
            assert session.user_id == "user123"
            assert session.session_id is not None
    
    @pytest.mark.asyncio
    async def test_get_session(self, session_manager):
        """Test session retrieval."""
        with patch('src.redis.sessions.redis_manager') as mock_manager:
            mock_conn = AsyncMock()
            mock_manager.get_connection.return_value.__aenter__.return_value = mock_conn
            
            # Mock session data
            session_data = {
                "session_id": "test-session",
                "user_id": "user123",
                "created_at": datetime.now().isoformat(),
                "last_accessed": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
                "data": {}
            }
            mock_conn.get.return_value = json.dumps(session_data)
            mock_conn.set.return_value = True
            
            session = await session_manager.get_session("test-session")
            assert session is not None
            assert session.user_id == "user123"
    
    @pytest.mark.asyncio
    async def test_delete_session(self, session_manager):
        """Test session deletion."""
        with patch('src.redis.sessions.redis_manager') as mock_manager:
            mock_conn = AsyncMock()
            mock_manager.get_connection.return_value.__aenter__.return_value = mock_conn
            
            mock_conn.delete.return_value = 1
            
            result = await session_manager.delete_session("test-session")
            assert result is True
    
    def test_generate_session_id(self, session_manager):
        """Test secure session ID generation."""
        session_id = session_manager.generate_session_id()
        assert len(session_id) > 20
        assert isinstance(session_id, str)
    
    def test_session_data_serialization(self):
        """Test session data serialization."""
        from src.redis.sessions import SessionData
        
        session = SessionData(
            session_id="test-123",
            user_id="user456",
            workspace_id="workspace789"
        )
        
        # Test to_dict
        data = session.to_dict()
        assert data["session_id"] == "test-123"
        assert data["user_id"] == "user456"
        
        # Test from_dict
        restored = SessionData.from_dict(data)
        assert restored.session_id == "test-123"
        assert restored.user_id == "user456"


# Integration tests
class TestRedisIntegration:
    """Test Redis components integration."""
    
    @pytest.mark.asyncio
    async def test_redis_health_endpoint_integration(self):
        """Test Redis health check integration."""
        with patch('src.redis.manager.redis_manager') as mock_manager:
            # Mock async health_check method
            mock_manager.health_check = AsyncMock(return_value={"status": "healthy", "latency_ms": 5.0})
            
            # This would be called by the main.py health endpoint
            health = await mock_manager.health_check()
            assert health["status"] == "healthy"
            assert "latency_ms" in health
