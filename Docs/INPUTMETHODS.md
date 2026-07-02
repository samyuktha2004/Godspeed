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
8. [Multimodal & OCR](#8-multimodal--ocr)
9. [Source Adapters (Reusable Pattern)](#9-source-adapters-reusable-pattern)
10. [Knowledge Graph Extraction](#10-knowledge-graph-extraction)
11. [Router & Ingestion Orchestration](#11-router--ingestion-orchestration)

> Section numbers 7 (Enterprise Data Sources) and 8.2 (Multimodal Document Analysis) were removed — no code backs them and they're out of scope for the current product (see §5.1 for why).

---

## 1. Architecture Overview

All input sources feed into a unified pipeline through a **hybrid two-layer architecture**:

```
Layer 1: Source-Specific Adapters
┌──────────────┬─────────────┬──────────────┬─────────────────┐
│ Confluence/  │ File/PDF    │ Web scraper  │ Local log       │
│ Jira agents  │ agent       │ (on-demand)  │ tailer (on-demand)│
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

All sources normalize their output to a `RawDocument` before entering the pipeline. Key fields include: `uri` (unique per source), `source_type`, `source_subtype`, `title`, `content` (plaintext or markdown), `content_hash` (SHA256 for change detection), `created_at`/`updated_at`, `author_ids` (for RBAC mapping), `space_id`, `parent_ids`, `tags`, `raw_metadata`, as well as `content_type`, `priority` (1–5), `ttl_seconds` (for ephemeral data), and `source_config`.

### Adapter Pattern

Each source has an adapter that implements a common interface providing `connect`, `fetch_all` (full crawl for initial indexing), `fetch_incremental` (only changed/new items since last sync), `fetch_by_query` (if the source supports search), and `normalize` (converts source-native items to `RawDocument`). All source adapters inherit from `BaseSourceAdapter`.

---

## 2. Integration Patterns

Data sources fall into four patterns, each with different sync strategies:

| Pattern | Examples | Sync Method | Freshness | Use Case |
|---------|----------|-------------|-----------|----------|
| **API-based (ingested)** | Confluence, Jira | REST API + webhook + periodic incremental sync | Real-time (webhook) + 60 min (periodic) | Knowledge bases, tickets |
| **API-based (live lookup, not ingested)** | Notion, Slack, GitHub (extra) | On-demand REST API call per query via `POST /tools/chat`; Slack also has a query-time retrieval agent in the main pipeline | Real-time (always current, not persisted) | Ad-hoc search/read |
| **Event-driven** | GitHub webhooks, Jira webhooks, Confluence webhooks | Webhooks + Celery `critical` queue | Real-time | Changes, new content |
| **Polling (on-demand only)** | Server logs, web scraping (URL/sitemap) | Manually-triggered Celery task | On demand | Local log tailing, ad-hoc URL ingest |
| **Batch/upload** | PDFs, CSV, raw text, scanned docs, bulk imports | Direct upload or scheduled file watch | On demand | One-time docs, manual data entry |

---

## 3. API-Based Integrations

### 3.1 Notion (Live lookup implemented; ingestion pipeline not built)

**Status:** No ingestion pipeline — Notion pages are never chunked into Qdrant, unlike Confluence/Jira/File. But a working **live on-demand lookup tool** exists: `tools/tools/notion_tools.py` (`notion_search`, `notion_read_page`), reachable via `POST /tools/chat` (see [`ARCHITECTURE.md`](./ARCHITECTURE.md)). It calls the Notion API directly per request — no local index, no RBAC scoping, no citations in the main `/agent/query` answer pipeline.

**Gap:** promoting Notion to a real ingestion agent (chunking + GLiNER PII mask + BGE-M3 embed + Qdrant upsert, matching the Confluence/Jira/File pattern) is tracked in [`TODO.md`](./TODO.md).

---

### 3.2 Confluence (Implemented — Full Agent)

**Status:** Fully implemented in `src/confluence_agent/`. Heading-based chunking with breadcrumbs, table extraction, incremental CQL sync, and webhook support.

**What's built:**
- `adapter.py` — `fetch_page`, `fetch_space`, `fetch_incremental` (CQL) via Confluence REST API
- `chunker.py` — BeautifulSoup parses Confluence Storage Format; heading-split chunks prefixed with `[Space > Ancestor > Page]` breadcrumb; each table = 1 chunk
- `pipeline.py` — `ingest_page` / `ingest_space` → chunk → GLiNER PII mask → BGE-M3 embed → Qdrant upsert (idempotent)
- `router.py` — `POST /webhooks/confluence` (HMAC-SHA256 verified), `POST /confluence/sync/{space_key}`
- Celery beat task: `confluence_periodic_sync` — incremental sync of all configured spaces every 60 min

**Extension ideas:**
- Page version history (show how docs evolved)
- Comments as sub-chunks (discussion context)
- Attachment metadata (PDFs logged as "available but not indexed yet")

---

### 3.3 GitHub (Live lookup implemented; ingestion pipeline not built)

**Status:** There is no `src/github_agent/`, no PyGithub dependency, no repo/PR/README ingestion into Qdrant, and no `/webhooks/github` endpoint (the `SlackWebhookHandler`/GitHub webhook code in `src/integrations/webhooks.py` is dead — never imported by any router). What exists is the same live on-demand pattern as Notion: `tools/tools/github_tools.py` via `POST /tools/chat`, calling the GitHub REST API directly per request.

**Gap:** GitHub was called out as a "Core" source alongside Confluence/Jira in the original design docs but never got an ingestion agent. Tracked in [`TODO.md`](./TODO.md) "Backend — Not Yet Built" as a future candidate (same shape as the Notion ingestion item — README/CHANGELOG/PR ingestion would also unblock a real Dependency Tracker).

---

### 3.4 Slack (Live retrieval implemented; ingestion pipeline not built)

**Status:** No ingestion pipeline — Slack messages are never indexed into Qdrant. But **live query-time retrieval is implemented and wired into the main pipeline**: `agent/tools/slack_search.py:run_slack_search` is a real `slack_search_node` in `agent/graph.py`, selected by the planner alongside `doc_search`/`ticket_lookup`/etc. per query. There is also a separate on-demand lookup tool (`tools/tools/slack_tools.py`) behind `POST /tools/chat`.

**How the live pipeline agent works today:**
- Uses `SLACK_BOT_TOKEN`; scans up to 10 channels the bot has joined (`conversations.list` filtered to `is_member`)
- Keyword-matches the query against recent message history per channel (no semantic embedding, no persistence)
- RBAC: scoped only to channels the bot is a member of — there is no additional team/channel-permission mapping beyond that

**Known limitation:** the 10-channel cap and lack of persistence mean recall degrades as the workspace grows. A real ingestion pipeline (index messages into Qdrant like Confluence/Jira) would fix this — tracked in [`TODO.md`](./TODO.md) as a "nice to have," not committed, since live search already covers the common case.

---

### 3.5 Jira (Implemented — Full Agent)

**Status:** Fully implemented in `src/jira_agent/`. Real JQL pagination, ADF text extraction, comment chunking, webhook support.

**What's built:**
- `adapter.py` — `fetch_issue`, `fetch_all` (JQL cursor pagination), `fetch_incremental`; handles Atlassian Document Format (ADF) → plain text extraction
- `chunker.py` — chunk 0: issue body (`key + summary + status + priority + description`); chunks 1..N: one per comment with author attribution
- `pipeline.py` — `ingest_issue` / `ingest_project` → chunk → GLiNER PII mask → BGE-M3 embed → Qdrant upsert (idempotent)
- `router.py` — `POST /webhooks/jira` (HMAC-SHA256 verified), `POST /jira/sync/{project_key}`
- Celery tasks: `jira_process_issue` (queue=critical, webhook-triggered), `jira_sync_project` (queue=polling)

**Extension ideas:**
- Linked issues (create graph of "relates to", "blocks", "is blocked by")
- Custom fields (e.g., SLA, priority, effort)
- Issue transitions & status history (show how issues evolved)

---

## 4. Event-Driven Integrations

Data sources that push updates via webhooks or event streams.

### 4.1 GitHub Webhooks (Not built)

No `/webhooks/github` endpoint exists — corrected from an earlier "Implemented" claim in this doc. See §3.3.

---

### 4.2 Slack Events (Not built — not needed given live search)

No `POST /webhooks/slack` endpoint exists. Since query-time Slack retrieval already works via live API search (§3.4), a webhook-driven ingestion pipeline isn't planned unless the live-search approach proves insufficient at scale.

---

### 4.3 Jira Webhooks (IMPLEMENTED)

**Status:** Implemented in `src/jira_agent/router.py`.

- Endpoint: `POST /webhooks/jira`
- Verification: `X-Hub-Signature: sha256=<hmac>` checked against `JIRA_WEBHOOK_SECRET`
- Events handled: `jira:issue_created`, `jira:issue_updated`
- On receipt: extracts `issue.key` → dispatches `jira_process_issue.delay(key)` on Celery `critical` queue → returns 200 immediately
- Register in Jira Cloud admin → System → WebHooks → URL: `https://your-server.com/webhooks/jira`

### 4.3a Confluence Webhooks (IMPLEMENTED)

**Status:** Implemented in `src/confluence_agent/router.py`.

- Endpoint: `POST /webhooks/confluence`
- Verification: `X-Hub-Signature: sha256=<hmac>` checked against `CONFLUENCE_WEBHOOK_SECRET`
- Events handled: `page_created`, `page_updated`
- On receipt: extracts `page.id` + `space.key` → dispatches `confluence_process_page.delay(page_id, space_key)` on Celery `critical` queue → returns 200 immediately
- Register in Confluence Cloud → General Config → Webhooks → URL: `https://your-server.com/webhooks/confluence`

---

## 5. Polling & Scheduled Sync

### 5.1 Server Logs (Implemented, on-demand only)

`LogAggregatorAdapter` (`src/adapters/polling.py`) reads structured JSON log lines from a local file path (`settings.integrations.log_file_paths[service]`) — not ELK/Splunk, just local files — filters to `ERROR`/`WARN` entries, and converts each to a `RawDocument`. It's a real, working Celery task (`src/tasks/ingestion_tasks.py`), but **nothing schedules it automatically** — no Celery Beat entry exists for it. It only runs when triggered manually (`.delay(...)`).

`MetricsAdapter`, `ErrorTraceAdapter`, and `BusinessDataAdapter` in the same file are literal no-op stubs — each `fetch_incremental` always returns `[]` with a "placeholder implementation" log line. No Prometheus/Datadog/Sentry/Salesforce/NetSuite/SAP integration exists. Not needed at the current product stage (observability/APM and ERP/CRM integration are out of scope for an engineering-docs copilot) — removed from the roadmap rather than carried forward as a "design only" item.

---

## 6. Batch Upload & Manual Input

One-off or user-initiated data ingestion.

### 6.1 File Upload — PDF, DOCX, CSV, XML, HTML, TXT (IMPLEMENTED)

**Status:** Fully implemented in `src/file_agent/`. Replaces and extends the basic PDF-only upload.

**Supported formats:** `.pdf`, `.docx`, `.doc`, `.xml`, `.txt`, `.md`, `.csv`, `.xlsx`, `.xls`, `.html`, `.htm`

**Endpoints:**
- `POST /api/ingest/file` — upload a single file (multipart), dispatches `file_process_task` to Celery
- `POST /api/ingest/folder` — queue all supported files under a given folder path

**Pipeline per file:**
```
detect_format(path)
  → parser dispatch (pdf / docx / xml / csv / html / text)
  → chunk_file_content (word-window 400w for text; 1 chunk per table row)
  → GLiNER PII mask
  → BGE-M3 embed
  → Qdrant upsert (idempotent by file name)
```

**Parsers (`src/file_agent/parsers/`):**
| Format | Library | Notes |
|--------|---------|-------|
| PDF | pdfplumber | pytesseract OCR fallback when text < 50 chars per page |
| DOCX | python-docx | paragraphs + table blocks |
| XML | xml.etree | recursive node extraction with tag_path |
| CSV/XLSX | pandas | each row = 1 chunk |
| HTML | BeautifulSoup | heading sections + table blocks |
| TXT/MD | built-in | word-window chunks |

**File watcher:** `src/file_agent/watcher.py` — watchdog `Observer` watches `FILE_WATCH_FOLDER` and auto-dispatches on file create/modify.

---

### 6.2 Raw Text Input (Not built — low-effort future item)

No `POST /api/ingest/text` endpoint exists. Low-effort extension of the already-built `src/file_agent/` upload pattern (paste text instead of a file) — tracked in [`TODO.md`](./TODO.md) "Backend — Not Yet Built."

---

### 6.3 CSV/Structured Data Import (IMPLEMENTED)

**Status:** Implemented via `src/file_agent/` — `POST /api/ingest/file` handles CSV and XLSX. Each row becomes an individual chunk with column: value pairs, making rows individually retrievable.

For bulk business-record imports (orders, contacts, products), use the file agent upload endpoint directly. Custom domain-specific enrichment (order IDs → entity extraction) is an extension point.

---

### 6.4 Scanned Documents & OCR (NEW)

**Status:** Design only. Use multimodal LLM or Tesseract for OCR.

See **Section 8: Multimodal & OCR** below.

---

## 8. Multimodal & OCR

Handling images, scanned documents, and visual content.

### 8.1 Image OCR (scanned PDFs implemented; standalone images not needed)

OCR for scanned PDF pages is implemented in `src/file_agent/parsers/pdf.py`: when a PDF page has fewer than 50 chars of extracted text, the parser falls back to `pytesseract` via a `pymupdf` pixmap at 200 DPI — transparent within the normal file ingestion pipeline.

Standalone image upload (`POST /api/ingest/image`) and multimodal vision/layout analysis were part of the original design but aren't needed — PDF/DOCX ingestion already covers the vast majority of real documents, and standalone images are an edge case not worth the added surface area right now.

---

## 9. Source Adapters (Generic Pattern — Built but Unused)

`src/adapters/base.py` defines `BaseSourceAdapter`, an `AdapterRegistry` class, and `register_adapter()`/`get_adapter_registry()`. `src/ingestion/orchestrator.py`'s `IngestionOrchestrator.ingest_from_source(...)` is built on top of it. **Nothing in the codebase ever calls `register_adapter()`** — the registry is always empty at runtime, and none of the real ingestion agents (Confluence/Jira/File) go through this orchestrator; each has its own direct `pipeline.py`. Treat this as dead scaffolding, not the actual ingestion architecture — see [`ARCHITECTURE.md`](./ARCHITECTURE.md) for how ingestion really works (per-source agent, not shared adapter registry).

---

## 10. Knowledge Graph Extraction

**Status: Implemented** — see `graph_store/` (extractor.py, writer.py, reader.py, stream.py, api.py).

Entities and relationships are extracted from every ingested chunk and materialized into Neo4j for multi-hop context retrieval and graph visualization.

### 10.1 Entity Extraction (Gemini 2.5 Pro)

**Location:** `graph_store/extractor.py`

Entity extraction uses **Gemini 2.5 Pro** (not GLiNER — GLiNER is used only for PII masking pre-ingestion). A strict prompt schema prevents hallucination by whitelisting both entity types and relationship types.

**Whitelisted entity types:**
- `Service` — internal microservices, APIs
- `Library` — third-party packages, SDKs, frameworks
- `Incident` — outages, bugs, incidents with IDs
- `Team` — engineering teams that own services

**Whitelisted relationship types:**
- `MENTIONS` (Chunk → Service)
- `REFERENCES` (Chunk → Library)
- `DEPENDS_ON` (Service → Library)
- `OWNED_BY` (Service/Incident → Team)
- `CAUSED_BY` (Incident → Service)
- `HAS_CHUNK` (Document → Chunk)
- `DOCUMENTS` (Document → Entity)

Any entity or relationship outside these whitelists is discarded — this is intentional. The graph is scoped to engineering topology, not general NLP entities.

### 10.2 Neo4j Graph Materialization

**Location:** `graph_store/writer.py`

All writes use Cypher `MERGE` for idempotency — re-ingesting the same chunk never duplicates nodes or edges.

```
Ingestion pipeline
    ↓
graph_store/extractor.py  — Gemini extracts entities + relationships from chunk text
    ↓
graph_store/writer.py     — MERGE nodes (Service/Library/Incident/Team/Chunk/Document)
                          — MERGE edges (DEPENDS_ON, CAUSED_BY, MENTIONS, etc.)
    ↓
Neo4j (production graph)
```

**Node indexes** (created on first ingest):
- `Chunk.chunk_id`, `Document.doc_id`, `Incident.incident_id`
- `Team.team_id`, `Service(name, team_id)`, `Library.name`

### 10.3 Graph Traversal at Query Time

**Location:** `graph_store/reader.py`

Multi-path traversal queries are used at query time to augment retrieval context. Paths:

| Start entity | Traversal path | Result |
|---|---|---|
| Incident | `(i)−[CAUSED_BY]→(svc)−[DEPENDS_ON]→(lib)←[REFERENCES]−(chunk)` | All chunks about the incident's root cause service and its libraries |
| Service | `(svc)←[MENTIONS]−(chunk)`, `(svc)−[DEPENDS_ON]→(lib)←[REFERENCES]−(chunk)` | All chunks mentioning or about the service |
| Library | `(lib)←[REFERENCES]−(chunk)` | All chunks referencing the library |

Results are deduplicated and union-merged across traversal paths before being passed to the synthesis agent.

### 10.4 Graph Streaming to Frontend

**Location:** `graph_store/stream.py`

WebSocket endpoint `WS /graph/stream` — streams the graph to the frontend node-by-node and edge-by-edge with 50ms delays. Events:

```json
{"event": "node", "id": "...", "label": "Service", "name": "auth-service"}
{"event": "edge", "from": "...", "to": "...", "rel": "DEPENDS_ON"}
{"event": "done", "nodes_count": 42, "edges_count": 87}
```

For the results page, the frontend calls `GET /graph/traverse?entity=<name>&type=<Service|Library|Incident>` for each entity cited in the SSE answer, then renders a query-scoped subgraph — not the full graph dump.

---

## 11. Router & Ingestion Enrichment (superseded by real implementations)

`src/retrieval/router.py` (query-time `DocumentRouter`) and `src/ingestion/enrichment.py` (`DocumentEnricher`) described in earlier drafts of this doc **do not exist** — this was speculative design later replaced by real, different implementations:

- **Query-time routing:** the real router is `agent/agents/router.py` — deterministic, no LLM call, narrows scope from a per-team manifest. See [`metadata-scaling-up/01_query_routing_layer.md`](./metadata-scaling-up/01_query_routing_layer.md).
- **Ingest-time entity extraction:** happens per-agent (Confluence/Jira/File pipelines each return entity graph nodes) and is materialized by `graph_store/writer.py` using Gemini extraction (`graph_store/extractor.py`) — see §10 above. There's no separate document-category classifier.

---

## 12. Webhook Event Flow (generic pluggable pattern — not built, not needed)

Earlier drafts of this doc described a generic pluggable webhook framework — `AuthHandler`/`PayloadParser`/`FieldTransformer`/`RBACEngine` classes, a `process_webhook_event` Celery task that dispatches by source name, and a `config/webhooks.yaml` + database-override system for per-org customization. **None of this exists.** `process_webhook_event` is defined in `src/tasks/ingestion_tasks.py`/`src/celery_app.py` but nothing calls it, and no `AuthHandler`/`PayloadParser`/`FieldTransformer`/`RBACEngine` classes exist anywhere.

What's real instead: each webhook (Jira, Confluence) is a plain FastAPI route in that source's own `router.py` that verifies its own HMAC signature and dispatches its own Celery task directly — see §4.3/4.3a above and [`ARCHITECTURE.md`](./ARCHITECTURE.md). This is simpler and sufficient at the current single-tenant scale; the generic pluggable-config layer isn't needed unless/until true multi-tenant per-org customization becomes a requirement.

---

## Summary: Integration Priorities & Roadmap

| Phase | Sources | Key Features | Status |
|-------|---------|--------------|--------|
| **Phase 1** | Confluence, Jira, PDF/DOCX/CSV/XML/HTML/TXT | Full ingestion: webhooks, chunking, RBAC, Qdrant | ✅ Done — `src/jira_agent/`, `src/confluence_agent/`, `src/file_agent/` |
| **Phase 1 (live-lookup only)** | Notion, Slack, GitHub | On-demand API search/read, no ingestion | ✅ Done — `tools/` (`POST /tools/chat`); Slack also has a query-time retrieval agent in the main pipeline (`agent/tools/slack_search.py`) |
| **Phase 2** | Notion, GitHub ingestion pipelines | Bring both to full-ingestion parity with Confluence/Jira | See [`TODO.md`](./TODO.md) |
| **Phase 3** | Knowledge graph materialization | Neo4j, graph-aware retrieval, cross-domain reasoning | ✅ Done — `graph_store/` |

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

**Cache Layer:** `SyncStateCache` tracks the last sync timestamp per source/space. `CredentialCache` stores integration credentials with a TTL to prevent indefinite exposure. Both are in `src/redis/cache.py`.

**Task Queues:** `IngestQueue` in `src/redis/queues.py` accepts a source type, payload, RBAC tags, and priority level. Failed tasks are automatically retried with backoff and moved to a dead-letter queue after 3 failures.

**Distributed Locks:** `DistributedLock` in `src/redis/locks.py` acquires a named lock with a configurable timeout, preventing concurrent syncs of the same source. Always used inside a try/finally to guarantee release.

**State Management:** `WebhookProcessingState` in `src/redis/session_state.py` provides idempotency — it tracks whether a webhook ID has already been processed, preventing duplicate ingestion.

#### B. Celery Task Queue (`src/celery_app.py`)

Celery is configured with four priority queues — `critical` (10), `high` (7), `default` (5), `polling` (3), and `low` (1) — and task routes that send webhook tasks to `critical`, enrichment tasks to `high`, and polling tasks to `polling`.

**Correction:** there is no Celery Beat schedule for Slack sync, log polling, or metrics polling — no `beat_schedule` entries exist for any of `src/tasks/ingestion_tasks.py`'s tasks. The only real periodic jobs are `confluence_periodic_sync` (60 min) and the nightly CAG job — see [`anomaly-and-forecasting/04_jobs_and_scheduling.md`](./anomaly-and-forecasting/04_jobs_and_scheduling.md) and `src/confluence_agent/tasks.py`. Web scraping, log aggregation, and Jira/File sync tasks are real and callable but must be triggered manually or via an API call, not on a timer.

#### C. Web Scraping (`src/adapters/web_scraper.py`)

`WebScraperAdapter.fetch_url(url)` fetches a single URL and returns a `RawDocument` with extracted text, title, and metadata. `SitemapAdapter.fetch_all(base_url)` fetches `sitemap.xml`, crawls all listed URLs respecting rate limits, and returns a list of `RawDocument` instances. Both can be dispatched as Celery tasks (`scrape_url.delay(url)`, `scrape_sitemap.delay(base_url)`) and monitored via the Flower UI at `http://localhost:5555`.

#### D. Polling Adapters (`src/adapters/polling.py`)

`LogAggregatorAdapter.fetch_incremental(service, last_sync)` reads from a local log file and returns `RawDocument` instances for `ERROR`/`WARN` entries, including level, trace ID, and stack trace — callable on-demand, not scheduled. `MetricsAdapter`, `ErrorTraceAdapter`, and `BusinessDataAdapter` are no-op stubs (always return `[]`) and are not part of the current roadmap.

#### E. Webhook Handlers (`src/integrations/webhooks.py`)

`SlackWebhookHandler` verifies the Slack signing secret, then routes to `handle_message_event` (priority NORMAL) or `handle_app_mention_event` (priority CRITICAL). `GitHubWebhookHandler`, `JiraWebhookHandler`, and `LogWebhookHandler` follow the same verify → parse → create `RawDocument` → queue pattern.

#### F. Ingestion Orchestrator (`src/ingestion/orchestrator.py`)

`IngestionOrchestrator.ingest_from_source(source_type, space_id, credentials, mode)` coordinates the full flow: acquires a distributed lock to prevent concurrent syncs, tracks the last sync timestamp for incremental mode, fetches and ingests documents, and retries automatically with backoff.

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

# Start Celery worker — use ingestion.jobs.celery_app for all agent tasks
celery -A ingestion.jobs.celery_app worker \
  -Q critical,default,polling \
  --loglevel=info

# Start Beat scheduler (confluence 60min sync + cag nightly at 02:00)
celery -A ingestion.jobs.celery_app beat --loglevel=info

# Start webhook + sync API (all 3 agent routers)
uvicorn src.agents_app:app --port 8001 --reload

# Monitor (optional, web UI)
celery -A ingestion.jobs.celery_app flower --port=5555
```

### 13.5 Complete Example Flow

**Ingest a Confluence page (real, webhook-driven — the accurate example):**

1. Confluence page updated → Atlassian sends `POST /webhooks/confluence` (HMAC verified)
2. Handler extracts `page.id` + `space.key` → dispatches `confluence_process_page.delay(...)` on Celery `critical` queue
3. Celery worker processes → passes to `src/confluence_agent/pipeline.py`
4. Pipeline executes → chunk (heading-split + breadcrumbs) → GLiNER PII mask → BGE-M3 embed → Qdrant upsert
5. Result indexed → Qdrant + Supabase metadata

There is no equivalent webhook-driven flow for Slack today — see §3.4 for how Slack retrieval actually works (live query-time search, no ingestion).

**Monitor:**
- Flower UI shows task progress
- Redis CLI shows queue depth
- Logs show parsing/storage status

### 13.6 Failure Handling

Tasks retry up to 3 times with exponential backoff (60s, 120s, 180s). After all retries are exhausted, the task moves to the dead-letter queue (`ingest:deadletter` in Redis). Failed tasks can be inspected, fixed, and manually re-queued as needed.

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
| **Phase 2** | Celery tasks, webhooks (Jira/Confluence/File), on-demand polling (web scraper, local log tailing) | ✅ Ready — no automatic Beat schedule beyond `confluence_periodic_sync` and the nightly CAG job |
| **Phase 3** | KG materialization tasks | ✅ Done — `graph_store/` (writer.py Celery-compatible, reader.py traversal, stream.py WebSocket) |

