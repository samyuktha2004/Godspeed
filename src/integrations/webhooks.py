"""Webhook handlers for real-time event processing."""

import hashlib
import hmac
import logging
from datetime import datetime
from typing import Optional

from src.adapters.web_scraper import RawDocument
from src.redis.session_state import WebhookProcessingState
from src.redis.queues import WebhookQueue, Priority
import redis

logger = logging.getLogger(__name__)


class WebhookValidator:
    """Validate webhook signatures."""

    @staticmethod
    def verify_slack_signature(body: bytes, headers: dict, signing_secret: str) -> bool:
        """Verify Slack webhook signature."""
        timestamp = headers.get("X-Slack-Request-Timestamp", "")
        signature = headers.get("X-Slack-Request-Signature", "")

        if not timestamp or not signature:
            return False

        # Verify timestamp (within 5 minutes)
        try:
            req_time = int(timestamp)
            now = int(datetime.utcnow().timestamp())
            if abs(now - req_time) > 300:
                logger.warning(f"Slack request timestamp too old: {timestamp}")
                return False
        except ValueError:
            return False

        # Verify signature
        base_string = f"v0:{timestamp}:{body.decode('utf-8')}"
        computed_signature = "v0=" + hmac.new(
            signing_secret.encode(), base_string.encode(), hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(computed_signature, signature)

    @staticmethod
    def verify_github_signature(body: bytes, headers: dict, webhook_secret: str) -> bool:
        """Verify GitHub webhook signature."""
        signature = headers.get("X-Hub-Signature-256", "")

        if not signature:
            return False

        computed_signature = "sha256=" + hmac.new(
            webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(computed_signature, signature)

    @staticmethod
    def verify_jira_signature(body: bytes, headers: dict, webhook_secret: str) -> bool:
        """Verify Jira webhook signature."""
        signature = headers.get("X-Atlassian-Webhook-Signature", "")

        if not signature:
            return False

        computed_signature = hashlib.sha256(
            (body + webhook_secret.encode()).encode() if isinstance(body, str) else body + webhook_secret.encode()
        ).hexdigest()

        return hmac.compare_digest(computed_signature, signature)


class WebhookHandler:
    """Base webhook handler."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.validator = WebhookValidator()
        self.state = WebhookProcessingState(redis_client)
        self.queue = WebhookQueue(redis_client)

    async def create_raw_document(
        self,
        uri: str,
        source_type: str,
        source_subtype: str,
        title: str,
        content: str,
        author_id: str,
        space_id: str,
        tags: list = None,
        priority: int = 3,
    ) -> RawDocument:
        """Create a RawDocument from event data."""
        if tags is None:
            tags = []

        content_hash = hashlib.sha256(content.encode()).hexdigest()

        return RawDocument(
            uri=uri,
            source_type=source_type,
            source_subtype=source_subtype,
            title=title,
            content=content,
            content_hash=content_hash,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            author_ids=[author_id],
            space_id=space_id,
            tags=tags,
            priority=priority,
            raw_metadata={"webhook_source": source_type},
        )


class SlackWebhookHandler(WebhookHandler):
    """Handle Slack webhook events."""

    async def handle_message_event(self, payload: dict) -> Optional[RawDocument]:
        """
        Handle Slack message event.

        Args:
            payload: Slack event payload

        Returns:
            RawDocument if message should be indexed, None otherwise
        """
        event = payload.get("event", {})

        # Skip bot messages
        if event.get("bot_id") or event.get("subtype") in ["bot_message", "message_deleted"]:
            return None

        channel = event.get("channel", "unknown")
        user = event.get("user", "unknown")
        text = event.get("text", "")

        if not text:
            return None

        doc = await self.create_raw_document(
            uri=f"slack://msg/{channel}/{event.get('ts')}",
            source_type="slack",
            source_subtype="message",
            title=f"#{channel.lower()[:50]}: {text[:100]}",
            content=text,
            author_id=user,
            space_id=channel,
            tags=["slack", "message"],
            priority=2,
        )

        return doc

    async def handle_app_mention_event(self, payload: dict) -> Optional[RawDocument]:
        """Handle Slack app_mention event (higher priority)."""
        event = payload.get("event", {})
        text = event.get("text", "")

        if not text:
            return None

        doc = await self.create_raw_document(
            uri=f"slack://mention/{event.get('channel')}/{event.get('ts')}",
            source_type="slack",
            source_subtype="app_mention",
            title=f"@mention in #{event.get('channel')}: {text[:100]}",
            content=text,
            author_id=event.get("user", "unknown"),
            space_id=event.get("channel", "unknown"),
            tags=["slack", "mention", "important"],
            priority=4,
        )

        return doc


class GitHubWebhookHandler(WebhookHandler):
    """Handle GitHub webhook events."""

    async def handle_push_event(self, payload: dict) -> Optional[RawDocument]:
        """Handle GitHub push event."""
        repo_name = payload.get("repository", {}).get("full_name", "unknown")
        commits = payload.get("commits", [])

        if not commits:
            return None

        # Combine commit messages
        commit_messages = "\n".join([c.get("message", "") for c in commits])

        doc = await self.create_raw_document(
            uri=f"github://push/{repo_name}/{payload.get('after', 'unknown')[:7]}",
            source_type="github",
            source_subtype="push",
            title=f"Push to {repo_name}: {len(commits)} commits",
            content=commit_messages,
            author_id=payload.get("pusher", {}).get("name", "unknown"),
            space_id=repo_name,
            tags=["github", "push"],
            priority=2,
        )

        return doc

    async def handle_pull_request_event(self, payload: dict) -> Optional[RawDocument]:
        """Handle GitHub PR event."""
        action = payload.get("action", "")
        if action not in ["opened", "reopened", "synchronize"]:
            return None

        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {}).get("full_name", "unknown")

        content = f"""Title: {pr.get('title')}
State: {pr.get('state')}
Author: {pr.get('user', {}).get('login')}

Body:
{pr.get('body', 'N/A')}
"""

        doc = await self.create_raw_document(
            uri=f"github://pr/{repo}/{pr.get('number')}",
            source_type="github",
            source_subtype="pull_request",
            title=f"PR #{pr.get('number')} in {repo}: {pr.get('title')}",
            content=content,
            author_id=pr.get("user", {}).get("login", "unknown"),
            space_id=repo,
            tags=["github", "pr", action],
            priority=3,
        )

        return doc


class JiraWebhookHandler(WebhookHandler):
    """Handle Jira webhook events."""

    async def handle_issue_event(self, payload: dict) -> Optional[RawDocument]:
        """Handle Jira issue created/updated event."""
        event_type = payload.get("webhookEvent", "")
        if event_type not in ["jira:issue_created", "jira:issue_updated"]:
            return None

        issue = payload.get("issue", {})
        issue_key = issue.get("key", "unknown")
        project = issue.get("fields", {}).get("project", {}).get("key", "unknown")

        content = f"""Title: {issue.get('fields', {}).get('summary')}
Type: {issue.get('fields', {}).get('issuetype', {}).get('name')}
Status: {issue.get('fields', {}).get('status', {}).get('name')}
Priority: {issue.get('fields', {}).get('priority', {}).get('name')}
Assignee: {issue.get('fields', {}).get('assignee', {}).get('displayName', 'Unassigned')}

Description:
{issue.get('fields', {}).get('description', 'N/A')}
"""

        doc = await self.create_raw_document(
            uri=f"jira://{issue_key}",
            source_type="jira",
            source_subtype="issue",
            title=f"{issue_key}: {issue.get('fields', {}).get('summary', '')[:100]}",
            content=content,
            author_id=issue.get("fields", {}).get("reporter", {}).get("name", "unknown"),
            space_id=project,
            tags=["jira", event_type.split(":")[-1], issue_key],
            priority=3,
        )

        return doc


class LogWebhookHandler(WebhookHandler):
    """Handle application log webhook events."""

    async def handle_error_log(self, payload: dict) -> Optional[RawDocument]:
        """Handle ERROR/CRITICAL log entry."""
        level = payload.get("level", "").upper()
        if level not in ["ERROR", "CRITICAL"]:
            return None

        service = payload.get("service", "unknown")
        trace_id = payload.get("trace_id", "unknown")
        message = payload.get("message", "")

        content = f"""Level: {level}
Service: {service}
Trace ID: {trace_id}

Message: {message}

Context:
{payload.get('context', {})}

Stack Trace:
{payload.get('stacktrace', 'N/A')}
"""

        doc = await self.create_raw_document(
            uri=f"logs://{service}/{trace_id}",
            source_type="log",
            source_subtype="error_log",
            title=f"[{level}] {service}: {message[:80]}",
            content=content,
            author_id="system",
            space_id=service,
            tags=["logs", level.lower(), service],
            priority=5 if level == "CRITICAL" else 4,
        )

        return doc
