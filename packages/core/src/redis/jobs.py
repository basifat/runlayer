"""
Job Queue System - Scalable Validator Execution

Senior Engineer Principles:
- Performance: 1000+ jobs/second processing requirement
- Reliability: 99.9% job completion rate with retry logic
- Scalability: Horizontal scaling with multiple workers
- Production ready: Dead letter queues, monitoring, graceful shutdown
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass, asdict
import traceback

from .manager import redis_manager

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    DEAD = "dead"


class JobPriority(Enum):
    """Job priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Job:
    """Job definition with metadata."""
    id: str
    queue_name: str
    job_type: str
    payload: Dict[str, Any]
    priority: JobPriority = JobPriority.NORMAL
    max_retries: int = 3
    retry_count: int = 0
    timeout_seconds: int = 300
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: JobStatus = JobStatus.PENDING
    error_message: Optional[str] = None
    worker_id: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for Redis storage."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for field in ['created_at', 'started_at', 'completed_at']:
            if data[field]:
                data[field] = data[field].isoformat()
        # Convert enums to values
        data['priority'] = self.priority.value
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        """Create job from dictionary."""
        # Convert ISO strings back to datetime
        for field in ['created_at', 'started_at', 'completed_at']:
            if data.get(field):
                data[field] = datetime.fromisoformat(data[field])
        # Convert enum values back to enums
        if 'priority' in data:
            data['priority'] = JobPriority(data['priority'])
        if 'status' in data:
            data['status'] = JobStatus(data['status'])
        return cls(**data)


class JobQueue:
    """
    High-performance job queue with Redis backend.
    
    Features:
    - Priority-based job processing
    - Automatic retry with exponential backoff
    - Dead letter queue for failed jobs
    - Worker health monitoring
    - Graceful shutdown handling
    - Performance metrics and monitoring
    """
    
    def __init__(self, queue_name: str = "default"):
        self.queue_name = queue_name
        self.worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        self.is_running = False
        self.worker_task: Optional[asyncio.Task] = None
        self.job_handlers: Dict[str, Callable[[Job], Awaitable[Any]]] = {}
        
        # Queue keys
        self.pending_key = f"queue:{queue_name}:pending"
        self.processing_key = f"queue:{queue_name}:processing"
        self.completed_key = f"queue:{queue_name}:completed"
        self.failed_key = f"queue:{queue_name}:failed"
        self.dead_key = f"queue:{queue_name}:dead"
        self.jobs_key = f"queue:{queue_name}:jobs"
        self.workers_key = f"queue:{queue_name}:workers"
    
    def register_handler(self, job_type: str, handler: Callable[[Job], Awaitable[Any]]) -> None:
        """Register job handler for specific job type."""
        self.job_handlers[job_type] = handler
        logger.info(f"Registered handler for job type: {job_type}")
    
    async def enqueue(
        self, 
        job_type: str, 
        payload: Dict[str, Any],
        priority: JobPriority = JobPriority.NORMAL,
        max_retries: int = 3,
        timeout_seconds: int = 300
    ) -> str:
        """
        Add job to queue with priority support.
        
        Returns job ID for tracking.
        """
        job = Job(
            id=str(uuid.uuid4()),
            queue_name=self.queue_name,
            job_type=job_type,
            payload=payload,
            priority=priority,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds
        )
        
        try:
            async with redis_manager.get_connection() as redis_conn:
                # Store job data
                await redis_conn.hset(
                    self.jobs_key, 
                    job.id, 
                    json.dumps(job.to_dict())
                )
                
                # Add to priority queue (higher priority = higher score)
                await redis_conn.zadd(
                    self.pending_key, 
                    {job.id: priority.value}
                )
            
            logger.info(f"Enqueued job {job.id} with priority {priority.name}")
            return job.id
            
        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            raise
    
    async def dequeue(self, timeout: int = 10) -> Optional[Job]:
        """
        Dequeue highest priority job for processing.
        
        Uses BZPOPMAX for atomic, blocking dequeue with timeout.
        """
        try:
            async with redis_manager.get_connection() as redis_conn:
                # Atomic pop from priority queue (highest priority first)
                result = await redis_conn.bzpopmax(self.pending_key, timeout=timeout)
                
                if not result:
                    return None
                
                _, job_id, _ = result
                
                # Get job data
                job_data = await redis_conn.hget(self.jobs_key, job_id)
                if not job_data:
                    logger.warning(f"Job {job_id} not found in jobs hash")
                    return None
                
                job = Job.from_dict(json.loads(job_data))
                
                # Move to processing queue
                job.status = JobStatus.PROCESSING
                job.started_at = datetime.utcnow()
                job.worker_id = self.worker_id
                
                # Update job data
                await redis_conn.hset(
                    self.jobs_key,
                    job.id,
                    json.dumps(job.to_dict())
                )
                
                # Add to processing set with expiration
                await redis_conn.zadd(
                    self.processing_key,
                    {job.id: datetime.utcnow().timestamp()}
                )
                
                return job
                
        except Exception as e:
            logger.error(f"Failed to dequeue job: {e}")
            return None
    
    async def complete_job(self, job: Job, result: Any = None) -> None:
        """Mark job as completed."""
        try:
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            
            if result is not None:
                job.payload['result'] = result
            
            async with redis_manager.get_connection() as redis_conn:
                # Update job data
                await redis_conn.hset(
                    self.jobs_key,
                    job.id,
                    json.dumps(job.to_dict())
                )
                
                # Remove from processing, add to completed
                await redis_conn.zrem(self.processing_key, job.id)
                await redis_conn.zadd(
                    self.completed_key,
                    {job.id: datetime.utcnow().timestamp()}
                )
            
            logger.info(f"Job {job.id} completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to complete job {job.id}: {e}")
    
    async def fail_job(self, job: Job, error: str) -> None:
        """Handle job failure with retry logic."""
        try:
            job.error_message = error
            job.retry_count += 1
            
            async with redis_manager.get_connection() as redis_conn:
                # Remove from processing
                await redis_conn.zrem(self.processing_key, job.id)
                
                if job.retry_count <= job.max_retries:
                    # Retry with exponential backoff
                    job.status = JobStatus.RETRY
                    delay = min(300, 2 ** job.retry_count)  # Max 5 minutes
                    retry_time = datetime.utcnow() + timedelta(seconds=delay)
                    
                    # Schedule retry
                    await redis_conn.zadd(
                        self.pending_key,
                        {job.id: retry_time.timestamp()}
                    )
                    
                    logger.warning(f"Job {job.id} failed, retrying in {delay}s (attempt {job.retry_count}/{job.max_retries})")
                else:
                    # Move to dead letter queue
                    job.status = JobStatus.DEAD
                    await redis_conn.zadd(
                        self.dead_key,
                        {job.id: datetime.utcnow().timestamp()}
                    )
                    
                    logger.error(f"Job {job.id} moved to dead letter queue after {job.retry_count} failures")
                
                # Update job data
                await redis_conn.hset(
                    self.jobs_key,
                    job.id,
                    json.dumps(job.to_dict())
                )
                
        except Exception as e:
            logger.error(f"Failed to handle job failure for {job.id}: {e}")
    
    async def start_worker(self) -> None:
        """Start job processing worker."""
        if self.is_running:
            logger.warning("Worker already running")
            return
        
        self.is_running = True
        
        # Register worker
        try:
            async with redis_manager.get_connection() as redis_conn:
                await redis_conn.hset(
                    self.workers_key,
                    self.worker_id,
                    json.dumps({
                        "started_at": datetime.utcnow().isoformat(),
                        "queue_name": self.queue_name,
                        "status": "running"
                    })
                )
        except Exception as e:
            logger.error(f"Failed to register worker: {e}")
        
        # Start worker task
        self.worker_task = asyncio.create_task(self._worker_loop())
        logger.info(f"Worker {self.worker_id} started for queue {self.queue_name}")
    
    async def stop_worker(self) -> None:
        """Stop job processing worker gracefully."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        
        # Unregister worker
        try:
            async with redis_manager.get_connection() as redis_conn:
                await redis_conn.hdel(self.workers_key, self.worker_id)
        except Exception as e:
            logger.error(f"Failed to unregister worker: {e}")
        
        logger.info(f"Worker {self.worker_id} stopped")
    
    async def _worker_loop(self) -> None:
        """Main worker processing loop."""
        while self.is_running:
            try:
                # Dequeue job with timeout
                job = await self.dequeue(timeout=5)
                
                if not job:
                    continue
                
                # Check if handler exists
                if job.job_type not in self.job_handlers:
                    await self.fail_job(job, f"No handler for job type: {job.job_type}")
                    continue
                
                # Execute job with timeout
                try:
                    handler = self.job_handlers[job.job_type]
                    result = await asyncio.wait_for(
                        handler(job),
                        timeout=job.timeout_seconds
                    )
                    await self.complete_job(job, result)
                    
                except asyncio.TimeoutError:
                    await self.fail_job(job, f"Job timed out after {job.timeout_seconds} seconds")
                    
                except Exception as e:
                    error_msg = f"Job execution failed: {str(e)}\n{traceback.format_exc()}"
                    await self.fail_job(job, error_msg)
                
            except asyncio.CancelledError:
                logger.info("Worker loop cancelled")
                break
                
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(1)  # Brief pause before retrying
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics for monitoring."""
        try:
            async with redis_manager.get_connection() as redis_conn:
                pending_count = await redis_conn.zcard(self.pending_key)
                processing_count = await redis_conn.zcard(self.processing_key)
                completed_count = await redis_conn.zcard(self.completed_key)
                failed_count = await redis_conn.zcard(self.failed_key)
                dead_count = await redis_conn.zcard(self.dead_key)
                worker_count = await redis_conn.hlen(self.workers_key)
                
                return {
                    "queue_name": self.queue_name,
                    "pending_jobs": pending_count,
                    "processing_jobs": processing_count,
                    "completed_jobs": completed_count,
                    "failed_jobs": failed_count,
                    "dead_jobs": dead_count,
                    "active_workers": worker_count,
                    "registered_handlers": list(self.job_handlers.keys())
                }
                
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {"error": str(e)}
    
    async def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """Clean up old completed/failed jobs."""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        cutoff_timestamp = cutoff_time.timestamp()
        
        try:
            async with redis_manager.get_connection() as redis_conn:
                # Get old job IDs
                old_completed = await redis_conn.zrangebyscore(
                    self.completed_key, 0, cutoff_timestamp
                )
                old_failed = await redis_conn.zrangebyscore(
                    self.failed_key, 0, cutoff_timestamp
                )
                
                old_jobs = old_completed + old_failed
                
                if old_jobs:
                    # Remove from sorted sets
                    await redis_conn.zremrangebyscore(
                        self.completed_key, 0, cutoff_timestamp
                    )
                    await redis_conn.zremrangebyscore(
                        self.failed_key, 0, cutoff_timestamp
                    )
                    
                    # Remove job data
                    await redis_conn.hdel(self.jobs_key, *old_jobs)
                    
                    logger.info(f"Cleaned up {len(old_jobs)} old jobs")
                    return len(old_jobs)
                
                return 0
                
        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
            return 0


# Pre-configured job queues for different priorities
validator_queue = JobQueue("validators")
priority_queue = JobQueue("priority")
batch_queue = JobQueue("batch")
