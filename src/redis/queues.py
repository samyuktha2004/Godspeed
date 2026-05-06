"""Redis-backed task queues for document ingestion and webhook events."""

import json
from datetime import datetime
from typing import Optional
from enum import Enum

import redis
from pydantic import BaseModel


class Priority(str, Enum):
    """Task priority levels."""
    CRITICAL = "critical"  # Real-time (errors, alerts)
    HIGH = "high"          # Fast track (key decisions, breaking changes)
    NORMAL = "normal"      # Standard (routine data, logs)
    LOW = "low"            # Background (metrics, non-urgent)


class QueuedTask(BaseModel):
    """Task in a queue."""
    id: str
    source_type: str
    payload: dict
    rbac_tags: dict
    priority: Priority
    created_at: datetime
    attempt: int = 0
    max_retries: int = 3


class IngestQueue:
    """Queue for documents ready for ingestion pipeline."""

    def __init__(self, redis_client: redis.Redis, key_prefix: str = "ingest"):
        self.redis = redis_client
        self.key_prefix = key_prefix

    async def add(
        self,
        source_type: str,
        payload: dict,
        rbac_tags: dict,
        priority: Priority = Priority.NORMAL,
    ) -> str:
        """
        Add document to ingest queue.

        Uses sorted set with priority as score for ordering:
        - CRITICAL (0): real-time processing
        - HIGH (1): priority batch
        - NORMAL (2): standard batch
        - LOW (3): low-priority batch
        """
        task_id = f"{source_type}:{payload.get('uri', 'unknown')}:{datetime.utcnow().timestamp()}"

        priority_scores = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.NORMAL: 2,
            Priority.LOW: 3,
        }

        task = {
            "id": task_id,
            "source_type": source_type,
            "payload": json.dumps(payload),
            "rbac_tags": json.dumps(rbac_tags),
            "priority": priority.value,
            "created_at": datetime.utcnow().isoformat(),
            "attempt": 0,
        }

        # Add to sorted set: score = priority (lower = higher priority)
        self.redis.zadd(
            f"{self.key_prefix}:queue",
            {json.dumps(task): priority_scores[priority]}
        )

        return task_id

    async def pop(self, batch_size: int = 10) -> list[QueuedTask]:
        """
        Pop highest-priority tasks from queue.
        Returns up to batch_size tasks, prioritizing CRITICAL > HIGH > NORMAL > LOW.
        """
        key = f"{self.key_prefix}:queue"
        tasks = []

        # Pop from lowest score (highest priority)
        for _ in range(batch_size):
            result = self.redis.zrange(key, 0, 0)  # Get first item
            if not result:
                break

            task_json = result[0].decode('utf-8')
            task_dict = json.loads(task_json)

            # Remove from queue
            self.redis.zrem(key, task_json)

            task = QueuedTask(
                id=task_dict["id"],
                source_type=task_dict["source_type"],
                payload=json.loads(task_dict["payload"]),
                rbac_tags=json.loads(task_dict["rbac_tags"]),
                priority=Priority(task_dict["priority"]),
                created_at=datetime.fromisoformat(task_dict["created_at"]),
                attempt=task_dict["attempt"],
            )
            tasks.append(task)

        return tasks

    async def requeue_on_failure(self, task: QueuedTask) -> bool:
        """
        Re-queue task if it hasn't exceeded max retries.
        Returns True if re-queued, False if max retries exceeded.
        """
        if task.attempt >= task.max_retries:
            # Send to deadletter queue
            await self.send_to_deadletter(task, "max_retries_exceeded")
            return False

        task.attempt += 1
        await self.add(
            task.source_type,
            task.payload,
            task.rbac_tags,
            task.priority,
        )
        return True

    async def send_to_deadletter(self, task: QueuedTask, reason: str):
        """Send task to deadletter queue for manual inspection."""
        dlq_key = f"{self.key_prefix}:deadletter"

        dlq_item = {
            "task": json.dumps(task.dict()),
            "reason": reason,
            "failed_at": datetime.utcnow().isoformat(),
        }

        self.redis.lpush(dlq_key, json.dumps(dlq_item))
        # Keep deadletter for 30 days
        self.redis.expire(dlq_key, 86400 * 30)

    async def get_stats(self) -> dict:
        """Get queue statistics."""
        key = f"{self.key_prefix}:queue"
        dlq_key = f"{self.key_prefix}:deadletter"

        queue_length = self.redis.zcard(key)
        dlq_length = self.redis.llen(dlq_key)

        return {
            "queue_length": queue_length,
            "deadletter_length": dlq_length,
            "total": queue_length + dlq_length,
        }


class WebhookQueue:
    """Queue for raw webhook events (before processing)."""

    def __init__(self, redis_client: redis.Redis, key_prefix: str = "webhooks"):
        self.redis = redis_client
        self.key_prefix = key_prefix

    async def add(
        self,
        event_type: str,
        payload: dict,
        priority: Priority = Priority.NORMAL,
    ) -> str:
        """Queue a raw webhook event for async processing."""
        event_id = f"{event_type}:{datetime.utcnow().timestamp()}"

        priority_scores = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.NORMAL: 2,
            Priority.LOW: 3,
        }

        event = {
            "id": event_id,
            "event_type": event_type,
            "payload": json.dumps(payload),
            "priority": priority.value,
            "received_at": datetime.utcnow().isoformat(),
        }

        # Add to sorted set by priority
        self.redis.zadd(
            f"{self.key_prefix}:pending",
            {json.dumps(event): priority_scores[priority]}
        )

        return event_id

    async def pop(self, batch_size: int = 5) -> list[dict]:
        """Pop highest-priority webhook events."""
        key = f"{self.key_prefix}:pending"
        events = []

        for _ in range(batch_size):
            result = self.redis.zrange(key, 0, 0)
            if not result:
                break

            event_json = result[0].decode('utf-8')
            event = json.loads(event_json)

            # Remove from queue
            self.redis.zrem(key, event_json)

            events.append(event)

        return events


def get_queue(queue_type: str, redis_client: redis.Redis) -> Optional[object]:
    """Factory function to get queue instance."""
    queues = {
        "ingest": IngestQueue,
        "webhook": WebhookQueue,
    }

    queue_class = queues.get(queue_type)
    if not queue_class:
        return None

    return queue_class(redis_client)
