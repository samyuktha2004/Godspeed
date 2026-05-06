# Input Methods Architecture & Integration Guide

> **Document purpose:** Complete specification for all data source integrations, organized by integration pattern. Defines how each source connects to the system, how data is normalized, and how source-specific quirks are handled through adapters. Reference this when adding a new data source.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Integration Patterns](#2-integration-patterns)
3. [API-Based Integrations](#3-api-based-integrations)
4. [Event-Driven Integrations](#4-event-driven-integrations)
5. [Polling & Scheduled Sync](#5-polling--scheduled-sync)
6. [Batch Upload & Manual Input](#6-batch-upload--manual-input)
7. [Enterprise Data Sources](#7-enterprise-data-sources)
8. [Multimodal & OCR](#8-multimodal--ocr)
9. [Source Adapters (Reusable Pattern)](#9-source-adapters-reusable-pattern)
10. [Knowledge Graph Extraction](#10-knowledge-graph-extraction)
11. [Router & Ingestion Orchestration](#11-router--ingestion-orchestration)

---

## 1. Architecture Overview

All input sources feed into a unified pipeline through a **hybrid two-layer architecture**:

```
Layer 1: Source-Specific Adapters
┌──────────────┬─────────────┬──────────────┬─────────────────┐
│ Notion API   │ Slack API   │ Database ORM │ Log Parsers     │
│ Crawler      │ Event Bot   │ Connectors   │ & Scrapers      │
└──────┬───────┴──────┬──────┴──────┬───────┴────────┬────────┘
       │              │             │                │
       ▼              ▼             ▼                ▼
       │         RawDocument        │ (normalized model)
       └─────────────┬──────────────┘
                     │
Layer 2: Generic Ingestion Pipeline
       ▼
┌─────────────────────────────────────────────────────────┐
│ Fetch → Parse (Docling) → PII Mask (GLiNER)            │
│ ↓ Chunk (Semantic) → Embed (BGE-M3) → Store (Qdrant)  │
│ ↓ Index (Postgres) → RBAC Tag → Metadata               │
└─────────────────────────────────────────────────────────┘
```

### RawDocument — Normalized Model

All sources output to this dataclass before entering the pipeline:

```python
@dataclass
class RawDocument:
    uri: str                    # Unique identifier per source
    source_type: str            # "notion" | "slack" | "jira" | "db" | "log" | etc
    source_subtype: str         # Optional: "error_trace" | "perf_metric" | "order" | etc
    title: str                  # Source-appropriate title
    content: str                # Plaintext or markdown
    content_hash: str           # SHA256 for change detection
    created_at: datetime        # When document was created
    updated_at: datetime        # Last modification (for incremental sync)
    author_ids: list[str]       # Source-native user IDs (for RBAC mapping)
    space_id: str               # Notion workspace / Slack workspace / DB schema, etc
    parent_ids: list[str]       # Hierarchy: Notion parent page, DB parent record, etc
    tags: list[str]             # Source-native labels or auto-extracted categories
    raw_metadata: dict          # Full source-native fields (preserves context)
    
    # New fields for expanded sources
    content_type: str           # "text" | "log" | "metric" | "transaction" | "trace"
    priority: int               # 1-5: critical logs/errors vs routine metrics
    ttl_seconds: int | None     # For ephemeral data (logs, metrics, sessions)
    source_config: dict         # Which integration endpoint/instance this came from
```

### Adapter Pattern

Each source has an adapter that implements this interface:

```python
class BaseSourceAdapter(ABC):
    """All source adapters inherit from this."""
    
    @abstractmethod
    async def connect(self, credentials: dict) -> None:
        """Authenticate and validate connection."""
        pass
    
    @abstractmethod
    async def fetch_all(self, space_id: str) -> list[RawDocument]:
        """Full crawl for initial indexing."""
        pass
    
    @abstractmethod
    async def fetch_incremental(
        self, 
        space_id: str, 
        last_sync_at: datetime
    ) -> list[RawDocument]:
        """Fetch only changed/new items since last sync."""
        pass
    
    @abstractmethod
    async def fetch_by_query(self, query: str) -> list[RawDocument]:
        """Search capability (if source supports it)."""
        pass
    
    def normalize(self, raw_item: dict) -> RawDocument:
        """Convert source-native item to RawDocument."""
        # Implemented per adapter
        pass
```

---

## 2. Integration Patterns

Data sources fall into four patterns, each with different sync strategies:

| Pattern | Examples | Sync Method | Freshness | Use Case |
|---------|----------|-------------|-----------|----------|
| **API-based** | Notion, Confluence, Slack, Jira, Google Docs, Supabase | REST/GraphQL API + polling | 30-60 min | Knowledge bases, tickets, conversations |
| **Event-driven** | GitHub webhooks, Slack events, Jira webhooks, real-time logs | Webhooks + event queue | Real-time | Changes, incidents, new data |
| **Polling/scheduled** | Server logs, metrics, database snapshots, financial reports | Scheduled Celery task | 5-60 min | Monitoring, analytics, reporting |
| **Batch/upload** | PDFs, CSV, raw text, scanned docs, bulk imports | Direct upload or scheduled file watch | On demand | One-time docs, manual data entry |

---

## 3. API-Based Integrations

### 3.1 Notion (Existing — Extended)

**Status:** Implemented. See `04_integrations_and_tech_stack.md` for core details.

**Extension ideas:**
- Database properties as structured metadata (for entity extraction)
- Synced databases across Notion → preserve back-references

```python
# src/adapters/notion.py
class NotionAdapter(BaseSourceAdapter):
    async def fetch_incremental(self, space_id, last_sync_at):
        # Existing implementation — no changes needed
        # Already handles workspace traversal and content hash comparison
        pass
```

---

### 3.2 Confluence (Existing — Extended)

**Status:** Implemented. See `04_integrations_and_tech_stack.md` for core details.

**Extension ideas:**
- Page version history (show how docs evolved)
- Comments as sub-chunks (discussion context)
- Attachment metadata (PDFs logged as "available but not indexed yet")

```python
# src/adapters/confluence.py
class ConfluenceAdapter(BaseSourceAdapter):
    async def fetch_incremental(self, space_id, last_sync_at):
        # Existing implementation
        pass
```

---

### 3.3 GitHub (Existing — Extended)

**Status:** Implemented. See `04_integrations_and_tech_stack.md` for core details.

**Extension ideas:**
- Commit message bodies (often contain architectural rationale)
- Discussion threads (GitHub Discussions API)
- Release notes with semantic versioning (Dependency Tracker input)

```python
# src/adapters/github.py
class GitHubAdapter(BaseSourceAdapter):
    async def fetch_by_query(self, query):
        """Search issues, PRs, discussions by keyword."""
        # Leverage GitHub search API for on-demand retrieval
        pass
```

---

### 3.4 Slack (NEW — High Priority)

**Status:** Design only. Real-time chat context for team decisions.

**What to index:**
- Public channels (not DMs — privacy)
- Messages containing decisions, links, code snippets, context
- Thread replies (threaded conversations are often richer than top-level)
- Files shared in Slack (metadata only — actual PDFs/images via separate upload)

**Authentication:**
```python
from slack_sdk import WebClient

slack = WebClient(token=settings.SLACK_BOT_TOKEN)
# Or OAuth: requires chat:read, channels:history, files:read scopes
```

**Adapter:**
```python
# src/adapters/slack.py
class SlackAdapter(BaseSourceAdapter):
    async def connect(self, credentials):
        self.client = WebClient(token=credentials['bot_token'])
        await self._validate_permissions()
    
    async def fetch_all(self, space_id: str) -> list[RawDocument]:
        """
        space_id = workspace_id (e.g., "C01KZ7XJXXX" for a channel)
        Crawl all public channels and their message history (configurable lookback).
        """
        docs = []
        
        # List all public channels
        channels_response = await self.client.conversations_list(
            exclude_archived=True,
            types="public_channel"
        )
        
        for channel in channels_response['channels']:
            channel_docs = await self._fetch_channel_messages(channel)
            docs.extend(channel_docs)
        
        return docs
    
    async def _fetch_channel_messages(self, channel: dict, days_back=30) -> list[RawDocument]:
        """Fetch recent messages from a channel."""
        docs = []
        channel_id = channel['id']
        cutoff_ts = (time.time() - days_back * 86400)
        
        cursor = None
        while True:
            messages = await self.client.conversations_history(
                channel=channel_id,
                oldest=cutoff_ts,
                cursor=cursor,
                limit=100
            )
            
            for msg in messages['messages']:
                # Skip bot messages, file shares, etc. Keep human context
                if msg.get('subtype') or msg.get('bot_id'):
                    continue
                
                # Extract threaded replies (often contain decisions)
                thread_docs = await self._fetch_thread(channel_id, msg['ts'])
                
                content = f"{msg['text']}\n\n" + '\n'.join([
                    f"> {t['text']}" for t in thread_docs
                ])
                
                doc = RawDocument(
                    uri=f"slack://msg/{channel_id}/{msg['ts']}",
                    source_type="slack",
                    source_subtype="message",
                    title=f"#{channel['name']} - {self._extract_summary(msg['text'])}",
                    content=content,
                    content_hash=sha256(content.encode()).hexdigest(),
                    created_at=datetime.fromtimestamp(float(msg['ts'])),
                    updated_at=datetime.fromtimestamp(float(msg['ts'])),
                    author_ids=[msg.get('user', 'unknown')],
                    space_id=channel['id'],
                    parent_ids=[],
                    tags=['public_channel', channel['name']],
                    raw_metadata=msg
                )
                docs.append(doc)
            
            if not messages.get('has_more'):
                break
            cursor = messages['response_metadata']['next_cursor']
        
        return docs
    
    async def _fetch_thread(self, channel_id: str, thread_ts: str) -> list[dict]:
        """Fetch replies in a thread."""
        response = await self.client.conversations_replies(
            channel=channel_id,
            ts=thread_ts,
            limit=50
        )
        return response['messages'][1:]  # Skip parent (already fetched)
    
    async def fetch_incremental(self, space_id, last_sync_at):
        """Fetch only messages since last sync."""
        # Similar to fetch_all but with older=last_sync_at timestamp filter
        pass
    
    def _extract_summary(self, text: str) -> str:
        """Extract first line or first 100 chars for title."""
        lines = text.split('\n')
        summary = lines[0][:100]
        return summary if summary else "(empty message)"
```

**RBAC & Privacy:**
- Index only channels the bot has access to (configured per workspace)
- Do NOT index DMs, private channels (without explicit opt-in)
- Slack user IDs → internal RBAC mapping

**Sync schedule:**
- Incremental: every 15 minutes (Slack conversations move fast)
- Full re-crawl: weekly

---

### 3.5 Jira (Existing — Extended)

**Status:** Partially implemented (basic issue indexing). Extend to linked entities and custom fields.

**Extension ideas:**
- Linked issues (create graph of "relates to", "blocks", "is blocked by")
- Custom fields (e.g., SLA, priority, effort)
- Issue transitions & status history (show how issues evolved)

```python
# src/adapters/jira.py
class JiraAdapter(BaseSourceAdapter):
    async def fetch_incremental(self, space_id, last_sync_at):
        """space_id = Jira project key (e.g., "BACKEND", "INFRA")"""
        # Existing: fetch closed/resolved issues only
        # Extension: also fetch issue transitions since last_sync_at
        pass
```

---

### 3.6 Google Docs & OneDrive (NEW — Optional)

**Status:** Design only. Shared documents as knowledge base.

**Authentication:**
```python
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Service account for org-wide access
docs_service = build('docs', 'v1', credentials=Credentials.from_service_account_file(...))
drive_service = build('drive', 'v3', credentials=...)
```

**Adapter sketch:**
```python
class GoogleDocsAdapter(BaseSourceAdapter):
    async def fetch_all(self, space_id: str) -> list[RawDocument]:
        """space_id = folder ID in Google Drive"""
        # 1. List all docs in folder (recursive)
        # 2. Fetch each doc via Docs API (preserves formatting)
        # 3. Convert to markdown
        pass
```

---

### 3.7 Supabase Neo4j Integration (NEW — Optional)

**Status:** Design only. For real-time entity relationships and graph traversal.

**Use case:** When adding structured data (orders, users, products), automatically extract relationships and query the graph during retrieval.

```python
# src/adapters/supabase.py
class SupabaseAdapter(BaseSourceAdapter):
    """
    Reads from Supabase Postgres + materializes a Neo4j graph.
    Entities are auto-extracted from relationships.
    """
    async def fetch_all(self, space_id: str) -> list[RawDocument]:
        """
        space_id = Supabase project ID / database schema
        1. Query all tables
        2. For each row: convert to RawDocument
        3. Extract entity relationships (foreign keys → edges)
        4. Upsert to Neo4j graph
        """
        pass
    
    async def fetch_incremental(self, space_id, last_sync_at):
        """Poll Postgres for updated_at > last_sync_at"""
        pass
```

---

## 4. Event-Driven Integrations

Data sources that push updates via webhooks or event streams.

### 4.1 GitHub Webhooks (Existing)

**Status:** Implemented. See `04_integrations_and_tech_stack.md`.

Listens for: push, pull_request (merged), release.

---

### 4.2 Slack Events (NEW)

**Status:** Design only. Real-time reaction to team decisions.

**Authentication:**
```
Slack App manifest YAML:
oauth_config:
  scopes:
    bot:
      - chat:read
      - channels:history
      - messages.read
events:
  bot_events:
    - message
    - app_mention
request_url: https://your-app.com/webhooks/slack
```

**Webhook handler:**
```python
# src/integrations/slack/webhooks.py

@router.post("/webhooks/slack")
async def slack_webhook(request: Request):
    """Handle Slack events in real-time."""
    
    # Verify Slack signature
    body = await request.body()
    signature = verify_slack_signature(body, request.headers)
    
    payload = await request.json()
    
    if payload['type'] == 'url_verification':
        # Slack challenge verification
        return {"challenge": payload['challenge']}
    
    event = payload['event']
    
    if event['type'] == 'message' and event['subtype'] != 'bot_message':
        # Queue for immediate re-indexing
        await reindex_queue.add(SlackMessageIndexTask(
            channel_id=event['channel'],
            message_ts=event['ts'],
            text=event['text']
        ))
    
    return {"status": "ok"}
```

---

### 4.3 Jira Webhooks (NEW)

**Status:** Design only. Trigger on issue created/updated/resolved.

**Webhook payload:**
```python
# src/integrations/jira/webhooks.py

@router.post("/webhooks/jira")
async def jira_webhook(request: Request):
    payload = await request.json()
    event_type = payload['webhookEvent']
    issue = payload['issue']
    
    if event_type == 'jira:issue_updated':
        await reindex_queue.add(JiraIssueReindexTask(
            project_key=issue['key'].split('-')[0],
            issue_id=issue['id']
        ))
    
    return {"status": "ok"}
```

---

### 4.4 Real-Time Logs via Webhook (NEW)

**Status:** Design only. For critical error logs.

**Pattern:** App sends log entries to `/webhooks/logs` endpoint as they occur.

```python
# src/integrations/logs/webhooks.py

@router.post("/webhooks/logs")
async def logs_webhook(request: Request):
    """
    Expected JSON:
    {
        "timestamp": "2026-05-06T12:30:45Z",
        "level": "ERROR" | "WARN" | "INFO",
        "service": "api-backend",
        "message": "Failed to process order",
        "trace_id": "abc123",
        "metadata": {...}
    }
    """
    payload = await request.json()
    
    # Only index ERROR and CRITICAL logs immediately
    if payload['level'] in ['ERROR', 'CRITICAL']:
        doc = RawDocument(
            uri=f"logs://{payload['service']}/{payload['trace_id']}",
            source_type="log",
            source_subtype="error_trace",
            title=f"[{payload['level']}] {payload['service']}: {payload['message']}",
            content=json.dumps(payload, indent=2),
            content_hash=sha256(json.dumps(payload).encode()).hexdigest(),
            created_at=datetime.fromisoformat(payload['timestamp']),
            updated_at=datetime.now(),
            author_ids=["system"],
            space_id=payload['service'],
            tags=[payload['level'], payload['service']],
            priority=5 if payload['level'] == 'CRITICAL' else 4,
            ttl_seconds=86400 * 7,  # Keep logs for 1 week
            raw_metadata=payload
        )
        await ingest_pipeline.run(doc)
    
    return {"status": "ok"}
```

---

## 5. Polling & Scheduled Sync

Data sources with no real-time push capability. Celery Beat tasks pull data on a schedule.

### 5.1 Server Logs (NEW)

**Status:** Design only. Aggregate logs from application servers.

**Sources:** syslog, application logs, Docker containers, Kubernetes pods.

**Pattern:**
```python
# src/adapters/logs.py
class LogAggregatorAdapter(BaseSourceAdapter):
    """Polls log files or log aggregation services."""
    
    async def fetch_incremental(self, space_id: str, last_sync_at: datetime) -> list[RawDocument]:
        """
        space_id = service name (e.g., "api-backend", "worker-queue")
        Fetch logs since last sync, filter by severity.
        """
        docs = []
        
        # Example: read from JSON log file (or query ELK/Splunk API)
        log_lines = await self._read_log_file(
            service=space_id,
            since=last_sync_at
        )
        
        for line in log_lines:
            log_entry = json.loads(line)
            
            # Only index errors and warnings (not every INFO log)
            if log_entry.get('level') not in ['ERROR', 'WARN']:
                continue
            
            content = f"""
Level: {log_entry['level']}
Service: {log_entry['service']}
Message: {log_entry['message']}

Trace ID: {log_entry.get('trace_id')}
Stack trace:
{log_entry.get('stacktrace', 'N/A')}

Context:
{json.dumps(log_entry.get('context', {}), indent=2)}
"""
            
            doc = RawDocument(
                uri=f"logs://{space_id}/{log_entry['trace_id']}",
                source_type="log",
                source_subtype="error_log",
                title=f"[{log_entry['level']}] {log_entry['service']}: {log_entry['message'][:80]}",
                content=content,
                content_hash=sha256(content.encode()).hexdigest(),
                created_at=datetime.fromisoformat(log_entry['timestamp']),
                updated_at=datetime.now(),
                author_ids=["system"],
                space_id=space_id,
                tags=[log_entry['level'], space_id],
                priority=5 if log_entry['level'] == 'ERROR' else 3,
                ttl_seconds=86400 * 7,
                raw_metadata=log_entry
            )
            docs.append(doc)
        
        return docs
```

**Celery task:**
```python
# src/tasks/ingest_tasks.py

@app.task
@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # Poll logs every 5 minutes
    sender.add_periodic_task(300, fetch_server_logs.s())

@app.task
async def fetch_server_logs():
    """Poll and ingest ERROR/WARN logs from all services."""
    for service in settings.MONITORED_SERVICES:
        adapter = LogAggregatorAdapter()
        last_sync = await state_store.get(f"logs:last_sync:{service}")
        docs = await adapter.fetch_incremental(service, last_sync)
        
        for doc in docs:
            await ingest_pipeline.run(doc)
        
        await state_store.set(f"logs:last_sync:{service}", datetime.now())
```

---

### 5.2 Performance Metrics (NEW)

**Status:** Design only. Time-series metrics: latency, error rates, throughput.

**Sources:** Prometheus, Datadog, New Relic, CloudWatch.

**Pattern:**
```python
# src/adapters/metrics.py
class MetricsAdapter(BaseSourceAdapter):
    """Polls metrics APIs for anomalies and trends."""
    
    async def fetch_incremental(self, space_id: str, last_sync_at: datetime) -> list[RawDocument]:
        """
        space_id = metric source (e.g., "prometheus", "datadog")
        Fetch metrics with anomalies or threshold breaches.
        """
        metrics = await self._query_metrics_api(
            source=space_id,
            since=last_sync_at,
            filter_anomalies=True
        )
        
        docs = []
        for metric in metrics:
            if metric['anomaly_score'] > 0.8:  # High anomaly
                doc = RawDocument(
                    uri=f"metrics://{space_id}/{metric['id']}",
                    source_type="metric",
                    source_subtype="anomaly",
                    title=f"🚨 {metric['name']}: {metric['current_value']} (normal: {metric['baseline']})",
                    content=f"""
Metric: {metric['name']}
Current value: {metric['current_value']}
Baseline: {metric['baseline']}
Anomaly score: {metric['anomaly_score']}
Tags: {', '.join(metric['tags'])}

Alert: {metric.get('alert_reason', 'N/A')}
Recommendation: {metric.get('recommendation', 'N/A')}
""",
                    content_hash=sha256(json.dumps(metric).encode()).hexdigest(),
                    created_at=datetime.fromisoformat(metric['timestamp']),
                    updated_at=datetime.now(),
                    author_ids=["system"],
                    space_id=space_id,
                    tags=[metric['name'], 'anomaly'],
                    priority=4 if metric['anomaly_score'] > 0.9 else 2,
                    ttl_seconds=86400 * 30,
                    raw_metadata=metric
                )
                docs.append(doc)
        
        return docs
```

**Celery task:**
```python
@app.task
def fetch_metrics_anomalies():
    """Poll metrics for anomalies every 15 minutes."""
    adapter = MetricsAdapter()
    for source in ['prometheus', 'datadog']:
        docs = await adapter.fetch_incremental(
            source,
            datetime.now() - timedelta(minutes=15)
        )
        for doc in docs:
            await ingest_pipeline.run(doc)
```

---

### 5.3 Error Traces & Stack Traces (NEW)

**Status:** Design only. Structured error data from APM tools.

**Sources:** Sentry, Datadog APM, New Relic, Rollbar.

**Pattern:**
```python
# src/adapters/error_traces.py
class ErrorTraceAdapter(BaseSourceAdapter):
    """Polls APM services for new error groups."""
    
    async def fetch_incremental(self, space_id: str, last_sync_at: datetime) -> list[RawDocument]:
        """
        space_id = APM source (e.g., "sentry", "datadog")
        Fetch error groups with new occurrences since last sync.
        """
        error_groups = await self._query_apm_api(
            source=space_id,
            since=last_sync_at,
            sort_by='first_seen',
            status='unresolved'
        )
        
        docs = []
        for error in error_groups:
            # Only index if it's a new or recurring error
            if error['events_count'] > 3 or error['is_new']:
                doc = RawDocument(
                    uri=f"error://{space_id}/{error['id']}",
                    source_type="error_trace",
                    source_subtype=error['error_type'],
                    title=f"Error: {error['message'][:100]}",
                    content=f"""
Error Type: {error['error_type']}
Exception: {error['message']}
Occurrences: {error['events_count']}

Stack trace:
{error['stacktrace']}

Affected files:
{', '.join(error['affected_files'])}

First seen: {error['first_seen']}
Last seen: {error['last_seen']}

Reproduction steps (if available):
{error.get('reproduction_url', 'N/A')}
""",
                    content_hash=sha256(json.dumps(error).encode()).hexdigest(),
                    created_at=datetime.fromisoformat(error['first_seen']),
                    updated_at=datetime.fromisoformat(error['last_seen']),
                    author_ids=["system"],
                    space_id=space_id,
                    tags=[error['error_type'], space_id, 'error'],
                    priority=5 if error['events_count'] > 50 else 4,
                    ttl_seconds=86400 * 30,
                    raw_metadata=error
                )
                docs.append(doc)
        
        return docs
```

---

### 5.4 Financial Reports & Business Data (NEW)

**Status:** Design only. Structured business entities from ERP, CRM, inventory systems.

**Sources:** SAP, NetSuite, Salesforce, accounting systems, inventory DBs.

**Pattern:**
```python
# src/adapters/business_data.py
class BusinessDataAdapter(BaseSourceAdapter):
    """Connects to ERP/CRM systems via ORM."""
    
    async def fetch_incremental(self, space_id: str, last_sync_at: datetime) -> list[RawDocument]:
        """
        space_id = business domain (e.g., "sales", "inventory", "finance", "supply_chain")
        Fetch updated records since last sync.
        """
        # Use ORM to query the business system
        orm = get_orm_for_system(space_id)
        
        if space_id == "sales":
            # Fetch updated sales transactions
            records = await orm.query(
                'transactions',
                where=f"updated_at > '{last_sync_at}'"
            )
            docs = await self._transactions_to_documents(records)
        
        elif space_id == "inventory":
            # Fetch inventory updates (low stock alerts, etc)
            records = await orm.query(
                'inventory_items',
                where=f"updated_at > '{last_sync_at}' OR stock_level < {settings.LOW_STOCK_THRESHOLD}"
            )
            docs = await self._inventory_to_documents(records)
        
        elif space_id == "supply_chain":
            # Fetch orders, shipments, events
            records = await orm.query(
                'orders',
                where=f"updated_at > '{last_sync_at}' OR status IN ('pending', 'in_transit')"
            )
            docs = await self._orders_to_documents(records)
        
        elif space_id == "finance":
            # Fetch financial reports, transactions
            records = await orm.query(
                'financial_reports',
                where=f"created_at > '{last_sync_at}'"
            )
            docs = await self._financial_to_documents(records)
        
        return docs
    
    async def _transactions_to_documents(self, transactions: list) -> list[RawDocument]:
        docs = []
        for txn in transactions:
            doc = RawDocument(
                uri=f"business://sales/txn/{txn['id']}",
                source_type="business_data",
                source_subtype="sales_transaction",
                title=f"Order #{txn['order_id']}: {txn['customer']} - ${txn['amount']}",
                content=f"""
Order ID: {txn['order_id']}
Customer: {txn['customer']}
Amount: ${txn['amount']}
Items: {txn['item_count']}
Date: {txn['date']}
Status: {txn['status']}
Rep: {txn['sales_rep']}

Notes: {txn.get('notes', 'N/A')}
""",
                content_hash=sha256(json.dumps(txn).encode()).hexdigest(),
                created_at=datetime.fromisoformat(txn['date']),
                updated_at=datetime.fromisoformat(txn['updated_at']),
                author_ids=[txn.get('created_by', 'system')],
                space_id="sales",
                tags=['sales', txn['status']],
                priority=3,
                ttl_seconds=86400 * 365,  # Keep for 1 year (business record)
                raw_metadata=txn
            )
            docs.append(doc)
        return docs
```

---

## 6. Batch Upload & Manual Input

One-off or user-initiated data ingestion.

### 6.1 PDF Upload (Existing)

**Status:** Implemented. See `04_integrations_and_tech_stack.md`.

---

### 6.2 Raw Text Input (NEW)

**Status:** Design only. User pastes or uploads raw text/markdown.

**Endpoint:**
```python
# src/api/ingest.py

@router.post("/api/ingest/text")
async def ingest_text(
    title: str = Form(...),
    content: str = Form(...),
    access_level: str = Form("team"),
    source_reference: str = Form(None),  # e.g., "email from John", "Slack discussion"
    user: User = Depends(get_current_user)
):
    """
    Ingest raw text/markdown directly.
    """
    doc = RawDocument(
        uri=f"manual://text/{uuid4()}",
        source_type="manual",
        source_subtype="raw_text",
        title=title,
        content=content,
        content_hash=sha256(content.encode()).hexdigest(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        author_ids=[user.id],
        space_id=user.team_id,
        tags=['manual-input', source_reference or 'unknown'],
        raw_metadata={
            'uploaded_by': user.id,
            'uploaded_at': datetime.now().isoformat(),
            'source_reference': source_reference
        }
    )
    doc.metadata.rbac_level = access_level
    
    task_id = await ingest_pipeline.run_async(doc)
    return {"task_id": task_id, "status": "queued", "uri": doc.uri}
```

---

### 6.3 CSV/Structured Data Import (NEW)

**Status:** Design only. Bulk upload of records (orders, contacts, etc).

**Endpoint:**
```python
@router.post("/api/ingest/csv")
async def ingest_csv(
    file: UploadFile = File(...),
    data_type: str = Form("orders"),  # orders | contacts | products | etc
    user: User = Depends(get_current_user)
):
    """
    Parse CSV and import as business records.
    """
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))
    
    # Convert each row to RawDocument
    docs = []
    for idx, row in df.iterrows():
        doc = RawDocument(
            uri=f"import://csv/{data_type}/{uuid4()}",
            source_type="csv_import",
            source_subtype=data_type,
            title=f"{data_type.capitalize()} import row {idx}",
            content=row.to_markdown(),
            content_hash=sha256(row.to_json().encode()).hexdigest(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author_ids=[user.id],
            space_id=user.team_id,
            tags=['csv-import', data_type],
            raw_metadata=row.to_dict()
        )
        docs.append(doc)
    
    # Queue all docs for ingestion
    for doc in docs:
        await ingest_pipeline.run_async(doc)
    
    return {"imported_count": len(docs), "data_type": data_type}
```

---

### 6.4 Scanned Documents & OCR (NEW)

**Status:** Design only. Use multimodal LLM or Tesseract for OCR.

See **Section 8: Multimodal & OCR** below.

---

## 7. Enterprise Data Sources

Structured data from business systems via ORM.

### 7.1 ORM Pattern for Database Connections

All business systems use a generic ORM adapter:

```python
# src/orm/base.py
class BaseORM(ABC):
    """Connects to any business database or API."""
    
    @abstractmethod
    async def connect(self, config: dict) -> None:
        """Authenticate to the system."""
        pass
    
    @abstractmethod
    async def query(
        self,
        table: str,
        where: str = None,
        limit: int = 100
    ) -> list[dict]:
        """Execute a query, return rows as dicts."""
        pass
    
    @abstractmethod
    async def get_schema(self, table: str) -> dict:
        """Get schema info: column names, types, relationships."""
        pass
    
    @abstractmethod
    async def get_updated_since(
        self,
        table: str,
        timestamp_column: str,
        since: datetime
    ) -> list[dict]:
        """Query rows updated since timestamp."""
        pass

# Concrete implementations
class PostgresORM(BaseORM):
    """Direct Postgres connection via SQLAlchemy."""
    pass

class SalesforceORM(BaseORM):
    """Salesforce REST API."""
    pass

class NetSuiteORM(BaseORM):
    """NetSuite SuiteTalk API."""
    pass

class SAPOORM(BaseORM):
    """SAP OData API."""
    pass

class CustomAPIOR(BaseORM):
    """Generic REST API wrapper."""
    pass
```

**Usage:**
```python
# src/adapters/business_data.py
class BusinessDataAdapter(BaseSourceAdapter):
    async def connect(self, credentials: dict):
        system_type = credentials['system_type']  # 'salesforce', 'netsuite', 'postgres', etc
        
        orm_class = ORM_REGISTRY[system_type]
        self.orm = orm_class()
        await self.orm.connect(credentials)
    
    async def fetch_incremental(self, space_id: str, last_sync_at: datetime) -> list[RawDocument]:
        # space_id = domain: "sales", "inventory", "finance", "supply_chain"
        config = settings.BUSINESS_DATA_SOURCES[space_id]
        
        # Query the system using ORM
        records = await self.orm.query(
            table=config['table'],
            where=f"{config['updated_at_column']} > '{last_sync_at}'",
            limit=1000
        )
        
        # Convert to RawDocuments
        docs = [self._record_to_document(r, space_id) for r in records]
        return docs
```

---

### 7.2 Supported Business Domains

| Domain | Source System | Key Data | Use Case |
|--------|---------------|----------|----------|
| **Sales** | Salesforce, NetSuite, custom CRM | Orders, transactions, customer interactions | "What was the deal with client X?" |
| **Inventory** | ERP systems, warehouse management | Stock levels, SKUs, locations, low-stock alerts | "What's our stock of component Y?" |
| **Finance** | Accounting systems, ERP | Reports, GL entries, budgets, expenses | "What's our Q2 revenue by region?" |
| **Supply Chain** | Procurement, logistics, shipping | POs, invoices, shipments, customs docs, events | "Where's order #12345?" |
| **HR** | HRIS, payroll systems | Org structure, policies, training records (if accessible) | "Who reports to manager X?" |
| **Product** | Product management tools, feature DBs | Features, roadmap, release notes, customer feedback | "When does feature Z ship?" |

**Configuration example (.env):**
```bash
# Salesforce
SALESFORCE_INSTANCE_URL=https://mycompany.salesforce.com
SALESFORCE_CLIENT_ID=...
SALESFORCE_CLIENT_SECRET=...
SALESFORCE_USERNAME=...
SALESFORCE_PASSWORD=...

# NetSuite
NETSUITE_ACCOUNT_ID=...
NETSUITE_CLIENT_ID=...
NETSUITE_CLIENT_SECRET=...

# Direct Postgres (internal inventory DB)
INVENTORY_DB_URL=postgresql://user:pass@db-inventory.internal:5432/inventory

# Generic REST APIs
SUPPLY_CHAIN_API_URL=https://logistics-api.vendor.com
SUPPLY_CHAIN_API_KEY=...

BUSINESS_DATA_SYNC_INTERVAL_MINUTES=60  # How often to poll
```

---

## 8. Multimodal & OCR

Handling images, scanned documents, and visual content.

### 8.1 Image OCR & Analysis (NEW)

**Status:** Design only. Use Claude's vision capabilities or open-source Tesseract.

**Pattern:**
```python
# src/adapters/ocr.py
class OCRAdapter(BaseSourceAdapter):
    """Extract text from images and scanned documents."""
    
    async def connect(self, credentials: dict):
        # Could be: Claude API, Tesseract, or other vision model
        self.vision_model = get_vision_model(credentials.get('provider', 'claude'))
    
    async def process_image(self, image_path: str, context: str = None) -> RawDocument:
        """
        image_path: local file path or URL
        context: optional metadata (e.g., "financial report Q2 2026")
        
        Returns a document with extracted text + OCR confidence scores.
        """
        # Read image
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # Use vision model to extract text + analyze layout
        extraction = await self.vision_model.extract_text(
            image_data,
            include_layout=True,
            include_confidence=True
        )
        
        # Build document
        content = f"""
Source: {image_path}
Context: {context or 'N/A'}

[OCR Extraction]
{extraction['text']}

[Document Layout]
{extraction.get('layout_description', 'N/A')}

[OCR Confidence: {extraction.get('overall_confidence', 0):.1%}]
"""
        
        doc = RawDocument(
            uri=f"ocr://image/{sha256(image_data).hexdigest()}",
            source_type="image",
            source_subtype="scanned_document",
            title=f"OCR: {context or Path(image_path).name}",
            content=content,
            content_hash=sha256(content.encode()).hexdigest(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            author_ids=["system"],
            space_id="documents",
            tags=['ocr', 'scanned'],
            raw_metadata={
                'source_file': image_path,
                'ocr_confidence': extraction.get('overall_confidence', 0),
                'context': context
            }
        )
        return doc
    
    async def fetch_all(self, space_id: str) -> list[RawDocument]:
        """
        space_id = folder path (e.g., "/scans", "/financial_docs")
        Crawl all images in folder and extract text.
        """
        docs = []
        folder_path = Path(space_id)
        
        for image_file in folder_path.glob('**/*.{png,jpg,jpeg,tiff,pdf}'):
            doc = await self.process_image(str(image_file))
            docs.append(doc)
        
        return docs
```

**Endpoint for image upload:**
```python
@router.post("/api/ingest/image")
async def ingest_image(
    file: UploadFile = File(...),
    context: str = Form(None),  # "financial report", "whiteboard scan", etc
    user: User = Depends(get_current_user)
):
    """Upload an image for OCR and indexing."""
    content = await file.read()
    
    # Save temporarily
    temp_path = f"/tmp/{uuid4()}_{file.filename}"
    with open(temp_path, 'wb') as f:
        f.write(content)
    
    # Process
    ocr_adapter = OCRAdapter()
    doc = await ocr_adapter.process_image(temp_path, context)
    
    # Ingest
    task_id = await ingest_pipeline.run_async(doc)
    
    # Cleanup
    os.remove(temp_path)
    
    return {"task_id": task_id, "status": "queued"}
```

---

### 8.2 Multimodal Document Analysis (NEW)

**Status:** Design only. When documents contain images + text, analyze both.

**Pattern:**
```python
class MultimodalDocumentAdapter(BaseSourceAdapter):
    """
    Handles PDFs, Word docs, PowerPoints with embedded images and text.
    Extracts both text content and analyzes visuals (charts, diagrams, tables).
    """
    
    async def process_multimodal_doc(self, file_path: str) -> RawDocument:
        """
        1. Parse document (text + images)
        2. OCR images and extract text
        3. Analyze charts/tables visually
        4. Combine into structured document
        """
        # Use Docling to extract text + images
        parsed = await docling_parser.parse(file_path)
        
        # For each image: OCR + visual analysis
        image_analyses = []
        for image in parsed['images']:
            analysis = await self.vision_model.analyze_image(
                image,
                question="What does this visualization show? Extract any tables or charts."
            )
            image_analyses.append({
                'position': image['position'],
                'description': analysis['description'],
                'extracted_data': analysis.get('table_data', None)
            })
        
        # Combine
        combined_content = f"""
{parsed['text']}

[Visual Content Analysis]
{chr(10).join([f"- {a['description']}" for a in image_analyses])}

[Extracted Tables]
{chr(10).join([a['extracted_data'] for a in image_analyses if a['extracted_data']])}
"""
        
        doc = RawDocument(
            uri=f"multimodal://{sha256(file_path.encode()).hexdigest()}",
            source_type="document",
            source_subtype="multimodal",
            title=f"Multimodal: {Path(file_path).name}",
            content=combined_content,
            # ... rest of RawDocument fields
        )
        return doc
```

---

## 9. Source Adapters (Reusable Pattern)

All adapters inherit from `BaseSourceAdapter` and implement these methods. This ensures consistent behavior and easy extensibility.

### 9.1 Adapter Registry

```python
# src/adapters/__init__.py

ADAPTER_REGISTRY = {
    # Existing
    'notion': NotionAdapter,
    'confluence': ConfluenceAdapter,
    'github': GitHubAdapter,
    'jira': JiraAdapter,
    'pdf': PDFAdapter,
    'url': URLAdapter,
    
    # New
    'slack': SlackAdapter,
    'log': LogAggregatorAdapter,
    'metric': MetricsAdapter,
    'error_trace': ErrorTraceAdapter,
    'business_data': BusinessDataAdapter,
    'image': OCRAdapter,
    'csv_import': CSVImportAdapter,
    'raw_text': RawTextAdapter,
    'google_docs': GoogleDocsAdapter,
}

def get_adapter(source_type: str) -> BaseSourceAdapter:
    """Factory function to get the right adapter."""
    if source_type not in ADAPTER_REGISTRY:
        raise ValueError(f"Unknown source type: {source_type}")
    return ADAPTER_REGISTRY[source_type]()
```

---

### 9.2 Unified Ingestion Orchestrator

```python
# src/ingestion/orchestrator.py

class IngestionOrchestrator:
    """Routes documents through adapters and pipelines."""
    
    async def ingest_from_source(
        self,
        source_type: str,
        space_id: str,
        credentials: dict,
        mode: str = "incremental"  # or "full"
    ) -> IngestResult:
        """
        1. Get adapter for source
        2. Connect and authenticate
        3. Fetch documents
        4. Run through ingestion pipeline
        5. Return ingestion stats
        """
        adapter = get_adapter(source_type)
        await adapter.connect(credentials)
        
        if mode == "full":
            docs = await adapter.fetch_all(space_id)
        else:
            last_sync = await self._get_last_sync_time(source_type, space_id)
            docs = await adapter.fetch_incremental(space_id, last_sync)
        
        # Run pipeline
        results = []
        for doc in docs:
            try:
                result = await ingest_pipeline.run(doc)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to ingest {doc.uri}: {e}")
        
        # Update sync timestamp
        await self._set_last_sync_time(source_type, space_id, datetime.now())
        
        return IngestResult(
            source_type=source_type,
            space_id=space_id,
            docs_processed=len(docs),
            docs_successful=len(results),
            errors=[r for r in results if isinstance(r, Exception)]
        )
```

---

## 10. Knowledge Graph Extraction

Extracting entities and relationships from ingested documents for Area 5 (Knowledge Graph).

### 10.1 Automatic Entity Extraction

```python
# src/knowledge_graph/extractor.py

class EntityExtractor:
    """Uses GLiNER + custom patterns to extract entities."""
    
    async def extract_entities(self, doc: RawDocument) -> list[Entity]:
        """
        Extract entities from document content.
        Returns list of (entity_name, entity_type, confidence).
        """
        # Run GLiNER
        entities = await gliner_model.extract(
            doc.content,
            labels=["person", "organization", "service", "tool", "process", "product"]
        )
        
        # Add source-specific patterns
        if doc.source_type == "jira":
            # Extract issue IDs, project names
            entities.extend(self._extract_jira_entities(doc))
        elif doc.source_type == "github":
            # Extract repo names, PR numbers, issue numbers
            entities.extend(self._extract_github_entities(doc))
        elif doc.source_type == "business_data":
            # Extract order IDs, customer names, product SKUs
            entities.extend(self._extract_business_entities(doc))
        
        return entities
    
    def _extract_jira_entities(self, doc: RawDocument) -> list[Entity]:
        """Find Jira issue IDs (PROJ-123) and project names."""
        entities = []
        for match in re.finditer(r'([A-Z]+)-(\d+)', doc.content):
            project, issue_id = match.groups()
            entities.append(Entity(
                name=f"{project}-{issue_id}",
                type="jira_issue",
                confidence=0.95
            ))
        return entities
    
    def _extract_github_entities(self, doc: RawDocument) -> list[Entity]:
        """Find repo names, PR/issue references."""
        entities = []
        # Extract org/repo patterns
        for match in re.finditer(r'(\w+)\/(\w+)', doc.content):
            org, repo = match.groups()
            entities.append(Entity(
                name=f"{org}/{repo}",
                type="github_repo",
                confidence=0.9
            ))
        return entities
    
    def _extract_business_entities(self, doc: RawDocument) -> list[Entity]:
        """Extract domain-specific entities from raw_metadata."""
        entities = []
        metadata = doc.raw_metadata
        
        if 'order_id' in metadata:
            entities.append(Entity(
                name=metadata['order_id'],
                type="order",
                confidence=0.99
            ))
        if 'customer' in metadata:
            entities.append(Entity(
                name=metadata['customer'],
                type="customer",
                confidence=0.95
            ))
        
        return entities
```

### 10.2 Relationship Extraction

```python
# src/knowledge_graph/relationships.py

class RelationshipExtractor:
    """Extract relationships between entities using LLM."""
    
    async def extract_relationships(self, doc: RawDocument, entities: list[Entity]) -> list[Relationship]:
        """
        Analyze document to find relationships between extracted entities.
        Returns list of (entity_a, relation_type, entity_b).
        """
        if len(entities) < 2:
            return []
        
        # Use LLM to reason about relationships
        prompt = f"""
Document: {doc.title}
Content excerpt: {doc.content[:1000]}

Extracted entities: {[e.name for e in entities]}

What relationships exist between these entities?
Format: "Entity A → [relation type] → Entity B"

Examples:
- Order #123 → contains → Product SKU-456
- Service A → depends_on → Service B
- Employee John → works_for → Team DevOps
"""
        
        response = await claude.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        relationships = parse_relationships(response.content[0].text)
        return relationships
    
    def parse_relationships(self, text: str) -> list[Relationship]:
        """Parse LLM response into Relationship objects."""
        relationships = []
        for line in text.split('\n'):
            match = re.match(r'(\w+.*?)\s*→\s*\[(.+?)\]\s*→\s*(.*)', line)
            if match:
                source, relation_type, target = match.groups()
                relationships.append(Relationship(
                    source=source.strip(),
                    relation_type=relation_type.strip(),
                    target=target.strip()
                ))
        return relationships
```

### 10.3 Graph Materialization

```python
# src/knowledge_graph/materialization.py

class GraphMaterializer:
    """Persist entities and relationships to Neo4j."""
    
    async def upsert_entity(self, entity: Entity, source_doc: RawDocument):
        """Create or update entity in Neo4j."""
        query = """
MERGE (e:Entity {id: $entity_id})
SET e.name = $name,
    e.type = $type,
    e.confidence = $confidence,
    e.last_seen = datetime(),
    e.source_types = e.source_types + $source_type
RETURN e
"""
        await neo4j_driver.execute(query, {
            'entity_id': entity.name,
            'name': entity.name,
            'type': entity.type,
            'confidence': entity.confidence,
            'source_type': source_doc.source_type
        })
    
    async def upsert_relationship(self, rel: Relationship, source_doc: RawDocument):
        """Create or update relationship in Neo4j."""
        query = """
MATCH (source:Entity {id: $source_id}), (target:Entity {id: $target_id})
MERGE (source)-[r:RELATED {type: $relation_type}]->(target)
SET r.last_seen = datetime(),
    r.source_docs = r.source_docs + $source_uri,
    r.confidence = max(r.confidence, $confidence)
RETURN r
"""
        await neo4j_driver.execute(query, {
            'source_id': rel.source,
            'target_id': rel.target,
            'relation_type': rel.relation_type,
            'source_uri': source_doc.uri,
            'confidence': 0.8  # Relationship confidence
        })
```

---

## 11. Router & Ingestion Orchestration

How documents are routed to specialized agents and enriched with knowledge graph context.

### 11.1 Query-Time Router

```python
# src/retrieval/router.py

class DocumentRouter:
    """Route queries to the right retrieval strategy based on content."""
    
    async def route_query(self, user_query: str, user: User) -> RoutingDecision:
        """
        Analyze query to decide:
        - Which layers to search (T1/T2/T3)
        - Which source types to prioritize
        - Whether to inject knowledge graph context
        """
        
        # Classify query type
        query_type = await self._classify_query(user_query)  # lookup, troubleshooting, analytics, etc
        
        # Detect source preferences
        source_hints = self._detect_source_hints(user_query)  # "from Slack", "in Jira", etc
        
        # Build routing decision
        decision = RoutingDecision(
            query_type=query_type,
            search_layers=[],
            source_priority=[],
            inject_knowledge_graph=False
        )
        
        if query_type == "lookup":
            decision.search_layers = ["T1_semantic", "T1_keyword"]
            decision.source_priority = ["notion", "confluence", "github"]
        
        elif query_type == "troubleshooting":
            decision.search_layers = ["T1_semantic", "T1_keyword", "T3_live"]
            decision.source_priority = ["error_trace", "log", "github", "jira"]
            decision.inject_knowledge_graph = True  # Show related errors/services
        
        elif query_type == "business_analytics":
            decision.search_layers = ["T1_semantic"]
            decision.source_priority = ["business_data", "metric", "slack"]
            decision.inject_knowledge_graph = True  # Show entity relationships
        
        elif query_type == "cross_team":
            decision.search_layers = ["T1_semantic", "T1_keyword"]
            decision.source_priority = ["all"]  # Broad search across all sources
            decision.inject_knowledge_graph = True  # Find connections between teams
        
        return decision
    
    async def _classify_query(self, user_query: str) -> str:
        """Use LLM to classify query intent."""
        prompt = f"""
User query: "{user_query}"

Classify into one of:
- lookup: user is looking up factual information
- troubleshooting: user is debugging a problem
- business_analytics: user is asking about metrics/business data
- cross_team: user is finding connections between teams/services

Respond with only the classification.
"""
        response = await claude.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip().lower()
    
    def _detect_source_hints(self, user_query: str) -> list[str]:
        """Check if query mentions specific sources."""
        hints = []
        patterns = {
            'slack': r'\bslack\b',
            'jira': r'\b(jira|issue|bug)\b',
            'github': r'\b(github|repo|pr|pull request)\b',
            'confluence': r'\bconfluence\b',
            'error_trace': r'\b(error|stack trace|exception)\b',
            'log': r'\b(log|trace|debug)\b',
            'business_data': r'\b(order|invoice|transaction|customer)\b'
        }
        
        for source, pattern in patterns.items():
            if re.search(pattern, user_query, re.IGNORECASE):
                hints.append(source)
        
        return hints
```

### 11.2 Ingest-Time Enrichment

```python
# src/ingestion/enrichment.py

class DocumentEnricher:
    """Enrich documents with metadata, entities, relationships before storing."""
    
    async def enrich(self, doc: RawDocument) -> EnrichedDocument:
        """
        1. Extract entities and relationships
        2. Classify document category
        3. Detect dependencies/references
        4. Add domain-specific tags
        5. Materialize to knowledge graph
        """
        
        # Extract entities
        entity_extractor = EntityExtractor()
        entities = await entity_extractor.extract_entities(doc)
        
        # Extract relationships
        rel_extractor = RelationshipExtractor()
        relationships = await rel_extractor.extract_relationships(doc, entities)
        
        # Materialize to graph
        graph_materializer = GraphMaterializer()
        for entity in entities:
            await graph_materializer.upsert_entity(entity, doc)
        for rel in relationships:
            await graph_materializer.upsert_relationship(rel, doc)
        
        # Classify document
        category = await self._classify_document(doc)
        
        # Detect cross-references
        cross_refs = self._detect_cross_references(doc)
        
        enriched = EnrichedDocument(
            original_doc=doc,
            entities=entities,
            relationships=relationships,
            category=category,
            cross_references=cross_refs,
            enriched_at=datetime.now()
        )
        
        return enriched
    
    async def _classify_document(self, doc: RawDocument) -> str:
        """Classify document into category for better retrieval."""
        categories = ["runbook", "architecture", "incident_report", "feature_spec", "business_process"]
        
        prompt = f"""
Document: {doc.title}
Content: {doc.content[:500]}

Classify into one category: {', '.join(categories)}
Respond with only the category.
"""
        response = await claude.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip().lower()
    
    def _detect_cross_references(self, doc: RawDocument) -> list[str]:
        """Find references to other documents, services, entities."""
        refs = []
        
        # Jira issues
        refs.extend(re.findall(r'([A-Z]+)-(\d+)', doc.content))
        
        # GitHub repos
        refs.extend(re.findall(r'(\w+)/(\w+)', doc.content))
        
        # Service names
        for service in settings.KNOWN_SERVICES:
            if service in doc.content:
                refs.append(f"service:{service}")
        
        return refs
```

---

## 12. Webhook Event Flow & Agent Routing

### Webhook Handler Pattern (Core 80%)

All webhook endpoints follow this pattern:

```python
# src/integrations/{source}/webhooks.py

@router.post("/webhooks/{source_type}")
async def webhook_handler(request: Request):
    """
    Core webhook handler (80% - common for all sources).
    Extensible via pluggable auth, parsers, transformers, RBAC rules.
    """
    
    # 1. VERIFY (extension: auth handler)
    auth_handler = get_auth_handler(source_type)
    if not await auth_handler.verify_signature(request):
        return {"error": "Unauthorized"}, 401
    
    # 2. PARSE (extension: payload parser)
    payload = await request.json()
    parser = get_payload_parser(source_type)
    event_data = parser.extract_event(payload)
    
    # 3. CLASSIFY URGENCY
    priority = classify_priority(source_type, event_data)
    # priority: "critical" (real-time) or "normal/low" (batched)
    
    # 4. TRANSFORM (extension: field transformer)
    transformer = get_field_transformer(source_type)
    normalized_data = transformer.transform(event_data)
    
    # 5. APPLY RBAC (extension: RBAC rule engine)
    rbac_engine = get_rbac_engine(source_type)
    rbac_tags = await rbac_engine.tag_event(normalized_data)
    
    # 6. CHECK DUPLICATE (idempotency)
    content_hash = sha256(json.dumps(normalized_data).encode()).hexdigest()
    if await duplicate_checker.exists(content_hash):
        return {"status": "duplicate", "hash": content_hash}
    
    # 7. QUEUE FOR PROCESSING
    if priority == "critical":
        # Real-time: process immediately
        await process_webhook_event_immediate(source_type, normalized_data, rbac_tags)
    else:
        # Batched: add to queue
        await webhook_queue.add(source_type, normalized_data, rbac_tags, priority)
    
    return {"status": "queued", "priority": priority}
```

### Extension Points (20% Customization)

Each source can override these handlers for custom behavior:

```python
# src/integrations/{source}/extensions.py
# These are configured per-org via YAML + database overrides

class CustomAuthHandler(BaseAuthHandler):
    """Verify webhook signature (org-specific auth method)."""
    async def verify_signature(self, request):
        # Override for custom OAuth, API key schemes, etc.
        pass

class CustomPayloadParser(BasePayloadParser):
    """Extract event data from payload (handles custom webhook formats)."""
    def extract_event(self, payload):
        # Override for non-standard payload structures
        pass

class CustomFieldTransformer(BaseFieldTransformer):
    """Map source fields to RawDocument fields (org-specific field mapping)."""
    def transform(self, event_data):
        # E.g., map org's custom Jira fields to standard ones
        pass

class CustomRBACEngine(BaseRBACEngine):
    """Tag event with RBAC rules (org-specific team structure)."""
    async def tag_event(self, event_data):
        # E.g., route to specific team based on custom rules
        pass
```

### Webhook → Agent Routing

After queuing, Celery task routes to appropriate agent:

```python
# src/tasks/webhook_tasks.py

@app.task(bind=True, max_retries=3)
async def process_webhook_event(self, source_type: str, event_data: dict, rbac_tags: dict):
    """
    Route webhook event to the right Source Agent.
    Agent updates knowledge index and feeds into query-time retrieval.
    """
    
    # Get source agent (Slack Agent, GitHub Agent, etc.)
    agent_name = f"{source_type}_agent"
    agent = get_agent(agent_name)
    
    # Convert to RawDocument
    doc = RawDocument(
        uri=event_data['unique_id'],
        source_type=source_type,
        title=event_data['title'],
        content=event_data['content'],
        content_hash=sha256(json.dumps(event_data).encode()).hexdigest(),
        created_at=event_data['created_at'],
        updated_at=datetime.now(),
        author_ids=event_data['author_ids'],
        space_id=rbac_tags['space_id'],
        tags=event_data['tags'],
        priority=rbac_tags['priority'],
        ttl_seconds=rbac_tags.get('ttl_seconds'),
        raw_metadata=event_data
    )
    
    # Invoke Source Agent (LangGraph node)
    result = await agent.invoke({
        "document": doc,
        "rbac_tags": rbac_tags,
        "instruction": "ingest_and_index"
    })
    
    # Log result
    if result['status'] == 'success':
        logger.info(f"Webhook {source_type} ingested: {doc.uri}")
    else:
        logger.error(f"Webhook {source_type} failed: {result['error']}")
        raise self.retry(exc=Exception(result['error']), countdown=60)
```

### Configuration (YAML + Database)

```yaml
# config/webhooks.yaml
# Defines auth handlers, parsers, transformers, RBAC rules per source

webhooks:
  slack:
    auth_handler: slack_sig_verification  # Built-in or custom
    payload_parser: slack_events_api       # Built-in or custom
    field_transformer: slack_to_rawdoc     # Built-in or custom
    rbac_engine: slack_channel_rbac        # Built-in or custom
    priority:
      "message": "normal"
      "app_mention": "high"
      "reaction_added": "low"
    ttl_seconds: 2592000  # 30 days
    enabled: true
  
  github:
    auth_handler: github_hmac_sha256
    payload_parser: github_webhooks_api
    field_transformer: github_to_rawdoc
    rbac_engine: github_repo_team_rbac
    priority:
      "push": "high"
      "pull_request": "high"
      "release": "critical"
      "issues": "normal"
    ttl_seconds: null  # Keep indefinitely
    enabled: true
  
  jira:
    auth_handler: custom_jira_oauth  # Org-specific: uses their Jira instance
    payload_parser: jira_webhooks_api
    field_transformer: jira_custom_fields  # Org-specific: custom field mapping
    rbac_engine: jira_project_rbac
    priority:
      "issue_created": "high"
      "issue_updated": "normal"
    enabled: true

# Database overrides per org (allows customization without forking)
# Stored in PostgreSQL: webhooks_config table
# Example: "slack.field_transformer" → points to custom handler in their deployment
```

---

## Summary: Integration Priorities & Roadmap

| Phase | Sources | Key Features |
|-------|---------|--------------|
| **Phase 1 (Current)** | Notion, Confluence, GitHub, Jira, PDF, URL | Base adapter pattern, RawDocument model, generic ingestion pipeline |
| **Phase 2 (Next)** | Slack, logs, error traces, metrics | Event-driven ingestion, real-time alerting, RBAC for chat |
| **Phase 3** | Business data (sales, inventory, finance, supply chain) | ORM connectors, bulk sync, entity extraction for graph |
| **Phase 4** | Multimodal (OCR, images, scanned docs) | Vision model integration, document layout analysis |
| **Phase 5** | Knowledge graph materialization | Neo4j full implementation, graph-aware retrieval, cross-domain reasoning |

---

## 13. Implementation Infrastructure: Celery, Redis & Webscraping

### 13.1 Overview

The architecture described above is powered by a scalable, distributed task queue and caching system:

```
Data Sources & Webhooks
        ↓
   [Adapters] ← Web scraper, polling, webhooks
        ↓
Celery Task Queue (Redis-backed)
  - Priority routing (CRITICAL > HIGH > NORMAL > LOW)
  - Periodic polling via beat scheduler
  - Real-time webhook processing
  - Retry logic with exponential backoff
        ↓
Ingestion Pipeline
  (Parsing, chunking, embedding, storage)
```

### 13.2 Components

#### A. Redis Utilities (`src/redis/`)

**Cache Layer:**
```python
from src.redis.cache import SyncStateCache, CredentialCache

# Track last sync time per source
sync_state = SyncStateCache(redis_client)
last_sync = await sync_state.get_last_sync("slack", "workspace-123")

# Store integration credentials (TTL prevents exposure)
creds = CredentialCache(redis_client)
await creds.set_credentials("slack", "org-123", {"token": "xoxb-..."})
```

**Task Queues:**
```python
from src.redis.queues import IngestQueue, Priority

# Priority-ordered queue for documents
queue = IngestQueue(redis_client)
await queue.add(
    source_type="slack",
    payload=document.__dict__,
    rbac_tags={"channel": "general"},
    priority=Priority.CRITICAL  # Real-time processing
)

# Auto-retry with backoff, dead-letter queue after 3 failures
```

**Distributed Locks:**
```python
from src.redis.locks import DistributedLock

lock = DistributedLock(redis_client)
if await lock.acquire("slack:workspace-123", timeout_seconds=3600):
    # Prevents concurrent syncs of same source
    try:
        await adapter.fetch_incremental(space_id, last_sync)
    finally:
        await lock.release("slack:workspace-123")
```

**State Management:**
```python
from src.redis.session_state import WebhookProcessingState

state = WebhookProcessingState(redis_client)

# Idempotency: prevents re-processing duplicate webhooks
if not await state.is_completed("webhook-id-xyz"):
    await state.mark_processing("webhook-id-xyz")
    # Process webhook...
    await state.mark_completed("webhook-id-xyz", result)
```

#### B. Celery Task Queue (`src/celery_app.py`)

**Configuration:**
```python
# Queue definitions with priorities
app.conf.task_queues = (
    Queue("critical", priority=10),  # Webhooks (real-time)
    Queue("high", priority=7),       # Enrichment, important tasks
    Queue("default", priority=5),    # Standard polling
    Queue("polling", priority=3),    # Background syncs
    Queue("low", priority=1),        # Monitoring
)

# Task routing
app.conf.task_routes = {
    "tasks.webhooks.*": {"queue": "critical"},
    "tasks.enrichment.*": {"queue": "high"},
    "tasks.polling.*": {"queue": "polling"},
}
```

**Periodic Tasks (Beat Scheduler):**
```python
@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # Slack: every 15 minutes (chat moves fast)
    sender.add_periodic_task(900, sync_slack_incremental.s())
    
    # GitHub: every 1 hour
    sender.add_periodic_task(3600, sync_github_incremental.s())
    
    # Logs: every 5 minutes (real-time errors)
    sender.add_periodic_task(300, poll_server_logs.s())
    
    # Metrics: every 15 minutes (anomaly detection)
    sender.add_periodic_task(900, poll_metrics_anomalies.s())
```

#### C. Web Scraping (`src/adapters/web_scraper.py`)

**Single URL:**
```python
from src.adapters.web_scraper import WebScraperAdapter

adapter = WebScraperAdapter()
doc = await adapter.fetch_url("https://example.com/article")
# Returns RawDocument with extracted text, title, metadata
```

**Sitemap Crawling:**
```python
from src.adapters.web_scraper import SitemapAdapter

adapter = SitemapAdapter()
docs = await adapter.fetch_all("https://example.com")
# Fetches sitemap.xml, crawls all URLs, respects rate limits
```

**Via Celery:**
```python
from src.tasks.ingestion_tasks import scrape_url, scrape_sitemap

# Async (returns immediately, processed in background)
scrape_url.delay("https://example.com/page")
scrape_sitemap.delay("https://example.com")

# Monitor in Flower UI (http://localhost:5555)
```

#### D. Polling Adapters (`src/adapters/polling.py`)

**Server Logs:**
```python
from src.adapters.polling import LogAggregatorAdapter

adapter = LogAggregatorAdapter()
docs = await adapter.fetch_incremental("api-backend", last_sync)

# Reads from log file, extracts ERROR/WARN entries
# Returns RawDocuments with level, trace ID, stack trace
```

**Metrics, Errors, Business Data:**
```python
from src.adapters.polling import MetricsAdapter, ErrorTraceAdapter, BusinessDataAdapter

# Placeholders for integration with:
# - Prometheus, Datadog, New Relic (metrics)
# - Sentry, Datadog APM, New Relic (error traces)
# - Salesforce, NetSuite, ERP systems (business data)
```

#### E. Webhook Handlers (`src/integrations/webhooks.py`)

**Slack:**
```python
from src.integrations.webhooks import SlackWebhookHandler

handler = SlackWebhookHandler(redis_client)

# Verify webhook signature (prevents spoofing)
if handler.validator.verify_slack_signature(body, headers, signing_secret):
    # Handle different event types
    if event_type == "message":
        doc = await handler.handle_message_event(payload)
        priority = Priority.NORMAL
    elif event_type == "app_mention":
        doc = await handler.handle_app_mention_event(payload)
        priority = Priority.CRITICAL  # Real-time alerts
```

**GitHub, Jira, Logs:**
```python
from src.integrations.webhooks import (
    GitHubWebhookHandler, JiraWebhookHandler, LogWebhookHandler
)

# Same pattern: verify → parse → create RawDocument → queue
```

#### F. Ingestion Orchestrator (`src/ingestion/orchestrator.py`)

Coordinates all sources:
```python
from src.ingestion.orchestrator import IngestionOrchestrator

orchestrator = IngestionOrchestrator(redis_client)

result = await orchestrator.ingest_from_source(
    source_type="slack",
    space_id="workspace-123",
    credentials={"bot_token": "xoxb-..."},
    mode="incremental"
)

# Features:
# - Distributed lock (prevents concurrent syncs)
# - Last sync tracking (incremental vs full)
# - Automatic retry with backoff
# - Metrics & logging
```

### 13.3 Configuration

**Environment Variables (`src/config.py`):**

```bash
# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Integrations
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
GITHUB_TOKEN=ghp_...
GITHUB_WEBHOOK_SECRET=...
JIRA_INSTANCE_URL=https://company.atlassian.net
JIRA_API_TOKEN=...

# Polling intervals (seconds)
SLACK_POLL_INTERVAL=900
LOGS_POLL_INTERVAL=300
METRICS_POLL_INTERVAL=900

# Web scraping
WEB_SCRAPER_TIMEOUT=30
USER_AGENT=Godspeed-Bot/1.0
```

### 13.4 Startup Commands

```bash
# Start Redis
redis-server

# Start Celery worker (processes tasks)
celery -A src.celery_app worker \
  -Q critical,high,default,polling,webhooks \
  --loglevel=info

# Start Beat scheduler (periodic tasks)
celery -A src.celery_app beat --loglevel=info

# Monitor (optional, web UI)
celery -A src.celery_app flower --port=5555
```

### 13.5 Complete Example Flow

**Ingest Slack messages:**

1. **Setup webhook** in Slack dashboard → points to `POST /webhooks/slack`

2. **Receive event** → handler verifies signature → creates RawDocument

3. **Queue for processing** → IngestQueue with priority=CRITICAL

4. **Celery worker processes** → passes to ingestion pipeline

5. **Pipeline executes** → parse → chunk → embed → store

6. **Result indexed** → Postgres + Qdrant + Neo4j

**Monitor:**
- Flower UI shows task progress
- Redis CLI shows queue depth
- Logs show parsing/storage status

### 13.6 Failure Handling

**Automatic retry:**
```python
@app.task(bind=True, max_retries=3)
def process_webhook(self, ...):
    try:
        # Do work
    except Exception as e:
        # Retry with exponential backoff (60s, 120s, 180s)
        raise self.retry(exc=e, countdown=60)
```

**Dead-letter queue:**
```python
# After 3 failures, tasks move to DLQ
queue = IngestQueue(redis_client)
dlq_items = redis_client.lrange("ingest:deadletter", 0, -1)

# Inspect failed tasks, fix issue, manually re-queue if needed
```

### 13.7 Testing

```bash
# Test web scraper
python -c "
import asyncio
from src.adapters.web_scraper import WebScraperAdapter

adapter = WebScraperAdapter()
doc = asyncio.run(adapter.fetch_url('https://example.com'))
print(f'Title: {doc.title}')
print(f'Content length: {len(doc.content)}')
"

# Test polling
python -c "
import asyncio
from src.adapters.polling import LogAggregatorAdapter
from datetime import datetime, timedelta

adapter = LogAggregatorAdapter()
last_sync = datetime.utcnow() - timedelta(minutes=5)
docs = asyncio.run(adapter.fetch_incremental('api-backend', last_sync))
print(f'Found {len(docs)} log entries')
"

# Test Celery task
python -c "
from src.tasks.ingestion_tasks import scrape_url
task = scrape_url.delay('https://example.com')
print(f'Task ID: {task.id}')
# Check status in Flower
"
```

### 13.8 Integration with Phases

| Phase | Infrastructure | Status |
|-------|-----------------|--------|
| **Phase 1** | Config, adapters, orchestrator | ✅ Ready |
| **Phase 2** | Celery tasks, webhooks, polling | ✅ Ready |
| **Phase 3** | Business data adapters (placeholder) | 🔄 Extensible |
| **Phase 4** | OCR integration, multimodal | 🔄 Extensible |
| **Phase 5** | KG materialization tasks | 🔄 To implement |

---

*For detailed implementation guide, see: [WEBSCRAPING_CELERY_REDIS.md](../WEBSCRAPING_CELERY_REDIS.md)*

*Previous: [04_integrations_and_tech_stack.md](./04_integrations_and_tech_stack.md)*
*Reference: [01_problem_and_architecture.md](./01_problem_and_architecture.md) for Area 5 knowledge graph design*


