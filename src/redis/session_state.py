"""Session state management for API requests, webhook processing, and user interactions."""

import json
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

import redis


class SessionStateManager:
    """Manage session state in Redis (API sessions, webhook processing state, etc.)."""

    def __init__(self, redis_client: redis.Redis, key_prefix: str = "session"):
        self.redis = redis_client
        self.key_prefix = key_prefix

    def _make_session_key(self, session_id: str) -> str:
        """Build session key."""
        return f"{self.key_prefix}:{session_id}"

    async def create_session(
        self,
        user_id: str,
        org_id: str,
        ttl_seconds: int = 3600,
    ) -> str:
        """Create a new session."""
        session_id = str(uuid4())
        session_key = self._make_session_key(session_id)

        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "org_id": org_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
        }

        self.redis.setex(
            session_key,
            ttl_seconds,
            json.dumps(session_data),
        )

        return session_id

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Retrieve session data."""
        session_key = self._make_session_key(session_id)
        data = self.redis.get(session_key)

        if not data:
            return None

        return json.loads(data.decode('utf-8'))

    async def update_session(self, session_id: str, updates: dict, ttl_seconds: int = 3600):
        """Update session data."""
        session_key = self._make_session_key(session_id)
        session_data = await self.get_session(session_id)

        if not session_data:
            return False

        session_data.update(updates)
        session_data["last_activity"] = datetime.utcnow().isoformat()

        self.redis.setex(
            session_key,
            ttl_seconds,
            json.dumps(session_data),
        )

        return True

    async def delete_session(self, session_id: str):
        """Invalidate a session."""
        session_key = self._make_session_key(session_id)
        self.redis.delete(session_key)

    async def session_exists(self, session_id: str) -> bool:
        """Check if session is still valid."""
        session_key = self._make_session_key(session_id)
        return self.redis.exists(session_key) > 0


class WebhookProcessingState:
    """Track webhook processing state (for idempotency and retry logic)."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.key_prefix = "webhook_state"

    def _make_key(self, webhook_id: str) -> str:
        """Build key for webhook state."""
        return f"{self.key_prefix}:{webhook_id}"

    async def mark_processing(self, webhook_id: str, ttl_seconds: int = 86400):
        """Mark webhook as being processed."""
        key = self._make_key(webhook_id)
        state = {
            "webhook_id": webhook_id,
            "status": "processing",
            "started_at": datetime.utcnow().isoformat(),
        }

        self.redis.setex(key, ttl_seconds, json.dumps(state))

    async def mark_completed(self, webhook_id: str, result: dict):
        """Mark webhook as completed."""
        key = self._make_key(webhook_id)
        state = {
            "webhook_id": webhook_id,
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "result": result,
        }

        # Keep for 7 days after completion
        self.redis.setex(key, 86400 * 7, json.dumps(state))

    async def mark_failed(self, webhook_id: str, error: str, retry_at: Optional[datetime] = None):
        """Mark webhook as failed."""
        key = self._make_key(webhook_id)
        state = {
            "webhook_id": webhook_id,
            "status": "failed",
            "failed_at": datetime.utcnow().isoformat(),
            "error": error,
            "retry_at": retry_at.isoformat() if retry_at else None,
        }

        self.redis.setex(key, 86400 * 7, json.dumps(state))

    async def get_state(self, webhook_id: str) -> Optional[dict]:
        """Get current state of a webhook."""
        key = self._make_key(webhook_id)
        data = self.redis.get(key)

        if not data:
            return None

        return json.loads(data.decode('utf-8'))

    async def is_processing(self, webhook_id: str) -> bool:
        """Check if webhook is currently being processed."""
        state = await self.get_state(webhook_id)
        return state and state.get("status") == "processing"

    async def is_completed(self, webhook_id: str) -> bool:
        """Check if webhook has been completed (idempotency check)."""
        state = await self.get_state(webhook_id)
        return state and state.get("status") == "completed"


class AgentJobTracker:
    """Track agent job execution state (for orchestrator coordination)."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.key_prefix = "agent_jobs"

    def _make_job_key(self, job_id: str) -> str:
        """Build key for agent job."""
        return f"{self.key_prefix}:{job_id}"

    async def create_job(
        self,
        job_id: str,
        agent_name: str,
        input_data: dict,
        ttl_seconds: int = 3600,
    ):
        """Create a new agent job."""
        key = self._make_job_key(job_id)
        job = {
            "job_id": job_id,
            "agent_name": agent_name,
            "status": "queued",
            "input": json.dumps(input_data),
            "created_at": datetime.utcnow().isoformat(),
            "output": None,
        }

        self.redis.setex(key, ttl_seconds, json.dumps(job))

    async def mark_job_running(self, job_id: str):
        """Mark job as running."""
        key = self._make_job_key(job_id)
        job = json.loads(self.redis.get(key).decode('utf-8'))

        job["status"] = "running"
        job["started_at"] = datetime.utcnow().isoformat()

        self.redis.set(key, json.dumps(job))

    async def mark_job_completed(self, job_id: str, output: dict):
        """Mark job as completed with output."""
        key = self._make_job_key(job_id)
        job = json.loads(self.redis.get(key).decode('utf-8'))

        job["status"] = "completed"
        job["output"] = json.dumps(output)
        job["completed_at"] = datetime.utcnow().isoformat()

        self.redis.set(key, json.dumps(job))

    async def get_job(self, job_id: str) -> Optional[dict]:
        """Get job status and output."""
        key = self._make_job_key(job_id)
        data = self.redis.get(key)

        if not data:
            return None

        return json.loads(data.decode('utf-8'))

    async def is_job_complete(self, job_id: str) -> bool:
        """Check if job is completed."""
        job = await self.get_job(job_id)
        return job and job.get("status") == "completed"
