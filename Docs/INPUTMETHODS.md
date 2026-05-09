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

All sources normalize their output to a `RawDocument` before entering the pipeline. Key fields include: `uri` (unique per source), `source_type`, `source_subtype`, `title`, `content` (plaintext or markdown), `content_hash` (SHA256 for change detection), `created_at`/`updated_at`, `author_ids` (for RBAC mapping), `space_id`, `parent_ids`, `tags`, `raw_metadata`, as well as `content_type`, `priority` (1–5), `ttl_seconds` (for ephemeral data), and `source_config`.

### Adapter Pattern

Each source has an adapter that implements a common interface providing `connect`, `fetch_all` (full crawl for initial indexing), `fetch_incremental` (only changed/new items since last sync), `fetch_by_query` (if the source supports search), and `normalize` (converts source-native items to `RawDocument`). All source adapters inherit from `BaseSourceAdapter`.

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

### 3.3 GitHub (Existing — Extended)

**Status:** Implemented. See `04_integrations_and_tech_stack.md` for core details.

**Extension ideas:**
- Commit message bodies (often contain architectural rationale)
- Discussion threads (GitHub Discussions API)
- Release notes with semantic versioning (Dependency Tracker input)
- On-demand search across issues, PRs, and discussions via the GitHub search API

---

### 3.4 Slack (NEW — High Priority)

**Status:** Design only. Real-time chat context for team decisions.

**What to index:**
- Public channels (not DMs — privacy)
- Messages containing decisions, links, code snippets, context
- Thread replies (threaded conversations are often richer than top-level)
- Files shared in Slack (metadata only — actual PDFs/images via separate upload)

**Authentication:** Requires a Slack Bot Token (or full OAuth flow) with `chat:read`, `channels:history`, and `files:read` scopes.

The Slack adapter crawls all accessible public channels, paginates their message history, skips bot messages, fetches threaded replies, and combines thread content with the parent message before normalizing to `RawDocument`. Each message is keyed by `slack://msg/{channel_id}/{ts}`.

**RBAC & Privacy:**
- Index only channels the bot has access to (configured per workspace)
- Do NOT index DMs, private channels (without explicit opt-in)
- Slack user IDs → internal RBAC mapping

**Sync schedule:**
- Incremental: every 15 minutes (Slack conversations move fast)
- Full re-crawl: weekly

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

### 3.6 Google Docs & OneDrive (NEW — Optional)

**Status:** Design only. Shared documents as knowledge base.

The `GoogleDocsAdapter` authenticates via a service account for org-wide access (using `google-auth` and `googleapiclient`), then lists all documents under a given Drive folder recursively, fetches each via the Docs API to preserve formatting, and converts the result to markdown before normalizing to `RawDocument`.

---

### 3.7 Supabase Neo4j Integration (NEW — Optional)

**Status:** Design only. For real-time entity relationships and graph traversal.

**Use case:** When adding structured data (orders, users, products), automatically extract relationships and query the graph during retrieval.

The `SupabaseAdapter` reads all tables from a Supabase Postgres database, converts each row to a `RawDocument`, extracts entity relationships from foreign keys as graph edges, and upserts them to Neo4j. Incremental sync polls for rows where `updated_at > last_sync_at`.

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

The `POST /webhooks/slack` endpoint verifies the Slack request signature, handles the initial URL verification challenge, and on a `message` event (non-bot) queues a `SlackMessageIndexTask` for immediate re-indexing.

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

### 4.4 Real-Time Logs via Webhook (NEW)

**Status:** Design only. For critical error logs.

**Pattern:** App sends log entries to `POST /webhooks/logs` as they occur. The endpoint expects a JSON payload with fields `timestamp`, `level` (`ERROR` | `WARN` | `INFO`), `service`, `message`, `trace_id`, and `metadata`. Only `ERROR` and `CRITICAL` entries are normalized to `RawDocument` and immediately passed to the ingestion pipeline; lower-severity events are discarded at ingest time.

---

## 5. Polling & Scheduled Sync

Data sources with no real-time push capability. Celery Beat tasks pull data on a schedule.

### 5.1 Server Logs (NEW)

**Status:** Design only. Aggregate logs from application servers.

**Sources:** syslog, application logs, Docker containers, Kubernetes pods.

The `LogAggregatorAdapter` reads structured JSON log lines (or queries ELK/Splunk) for a given service since the last sync timestamp, filters to `ERROR` and `WARN` entries, and converts each to a `RawDocument` including the level, message, trace ID, stack trace, and context. A Celery Beat task polls all configured services every 5 minutes and updates the last-sync timestamp in the state store.

---

### 5.2 Performance Metrics (NEW)

**Status:** Design only. Time-series metrics: latency, error rates, throughput.

**Sources:** Prometheus, Datadog, New Relic, CloudWatch.

The `MetricsAdapter` queries a metrics API for anomalies since the last sync and indexes only entries with an anomaly score above 0.8. Each anomalous metric becomes a `RawDocument` containing the metric name, current value, baseline, anomaly score, tags, and any alert reason or recommendation. A Celery task polls all configured metric sources every 15 minutes.

---

### 5.3 Error Traces & Stack Traces (NEW)

**Status:** Design only. Structured error data from APM tools.

**Sources:** Sentry, Datadog APM, New Relic, Rollbar.

The `ErrorTraceAdapter` polls APM APIs for unresolved error groups with new occurrences since the last sync. It indexes error groups that are either newly seen or have more than 3 occurrences. Each group becomes a `RawDocument` with error type, exception message, occurrence count, stack trace, affected files, and first/last seen timestamps.

---

### 5.4 Financial Reports & Business Data (NEW)

**Status:** Design only. Structured business entities from ERP, CRM, inventory systems.

**Sources:** SAP, NetSuite, Salesforce, accounting systems, inventory DBs.

The `BusinessDataAdapter` uses an ORM connector to query rows updated since the last sync across four domains: `sales` (transactions), `inventory` (stock levels and low-stock alerts), `supply_chain` (orders and shipments), and `finance` (financial reports). Each record is converted to a `RawDocument` with domain-appropriate field mapping.

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

### 6.2 Raw Text Input (NEW)

**Status:** Design only. User pastes or uploads raw text/markdown.

The `POST /api/ingest/text` endpoint accepts a form-encoded `title`, `content`, optional `access_level` (default `team`), and optional `source_reference` (e.g., "email from John"). It normalizes the payload to a `RawDocument` with `source_type="manual"`, applies the requested RBAC level, and queues it through the ingestion pipeline, returning a `task_id` and URI.

---

### 6.3 CSV/Structured Data Import (IMPLEMENTED)

**Status:** Implemented via `src/file_agent/` — `POST /api/ingest/file` handles CSV and XLSX. Each row becomes an individual chunk with column: value pairs, making rows individually retrievable.

For bulk business-record imports (orders, contacts, products), use the file agent upload endpoint directly. Custom domain-specific enrichment (order IDs → entity extraction) is an extension point.

---

### 6.4 Scanned Documents & OCR (NEW)

**Status:** Design only. Use multimodal LLM or Tesseract for OCR.

See **Section 8: Multimodal & OCR** below.

---

## 7. Enterprise Data Sources

Structured data from business systems via ORM.

### 7.1 ORM Pattern for Database Connections

All business systems connect through a `BaseORM` interface that provides `connect`, `query` (table + optional WHERE clause + limit), `get_schema` (column names, types, relationships), and `get_updated_since` (rows updated after a given timestamp). Concrete implementations exist for Postgres (SQLAlchemy), Salesforce (REST API), NetSuite (SuiteTalk API), SAP (OData API), and a generic REST API wrapper.

The `BusinessDataAdapter` selects the appropriate ORM class at connect time based on `credentials['system_type']`, then uses it to fetch updated records per domain and convert them to `RawDocument` instances.

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

### 8.1 Image OCR & Analysis (PARTIALLY IMPLEMENTED)

**Status:** OCR for scanned PDF pages is implemented in `src/file_agent/parsers/pdf.py`. Full image-file OCR (standalone JPG/PNG) and multimodal layout analysis remain design-only.

**What's working:** When a PDF page has fewer than 50 chars of extracted text, the parser automatically falls back to `pytesseract` via a `pymupdf` pixmap at 200 DPI. This handles scanned PDFs transparently within the file ingestion pipeline.

**Still design-only:** Standalone image uploads (`POST /api/ingest/image`), multimodal vision analysis, document layout understanding.

The planned `OCRAdapter` would accept an image path (local or URL) and an optional context string, pass the image to a vision model (e.g., Gemini) to extract text and layout description with confidence scores, and return a `RawDocument`. A folder crawl variant would process all image files under a given directory. The `POST /api/ingest/image` endpoint would save the upload to a temp path, invoke the adapter, queue the result, and clean up the temp file.

---

### 8.2 Multimodal Document Analysis (NEW)

**Status:** Design only. When documents contain images + text, analyze both.

The `MultimodalDocumentAdapter` would use Docling to extract both text and embedded images from a file, pass each image to a vision model asking it to describe visualizations and extract table data, then combine the text and per-image analyses into a single `RawDocument` with sections for the main text, visual content descriptions, and extracted tables.

---

## 9. Source Adapters (Reusable Pattern)

All adapters inherit from `BaseSourceAdapter` and implement these methods. This ensures consistent behavior and easy extensibility.

### 9.1 Adapter Registry

The `ADAPTER_REGISTRY` dict in `src/adapters/__init__.py` maps source type strings (e.g., `'notion'`, `'slack'`, `'log'`, `'metric'`, `'business_data'`, `'image'`) to their adapter classes. A `get_adapter(source_type)` factory function instantiates the correct adapter or raises `ValueError` for unknown types.

---

### 9.2 Unified Ingestion Orchestrator

The `IngestionOrchestrator` in `src/ingestion/orchestrator.py` provides a single `ingest_from_source(source_type, space_id, credentials, mode)` entry point. It instantiates and connects the appropriate adapter, fetches documents (full or incremental based on `mode`), runs each through the ingestion pipeline, logs failures without aborting the batch, updates the last-sync timestamp, and returns an `IngestResult` with counts of processed and successful documents plus any errors.

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

## 11. Router & Ingestion Orchestration

How documents are routed to specialized agents and enriched with knowledge graph context.

### 11.1 Query-Time Router

The `DocumentRouter` in `src/retrieval/router.py` classifies each incoming user query by intent (lookup, troubleshooting, business_analytics, cross_team) using an LLM prompt, detects source hints from keywords in the query (e.g., "jira", "error", "order"), and returns a `RoutingDecision` specifying which search layers to query, which source types to prioritize, and whether to inject knowledge graph context. Troubleshooting and business analytics queries always enable graph injection.

### 11.2 Ingest-Time Enrichment

The `DocumentEnricher` in `src/ingestion/enrichment.py` runs after normalization and before storage. For each `RawDocument` it: extracts entities and relationships (via `EntityExtractor` and `RelationshipExtractor`), materializes them to the Neo4j graph via `GraphMaterializer`, classifies the document into a category (runbook, architecture, incident_report, feature_spec, business_process) using an LLM prompt, and detects cross-references to Jira issues, GitHub repos, and known service names.

---

## 12. Webhook Event Flow & Agent Routing

### Webhook Handler Pattern (Core 80%)

All webhook endpoints follow the same seven-step pattern: verify the request signature via an auth handler, parse the payload to extract event data, classify urgency (critical for real-time processing, normal/low for batched), transform fields to a normalized form, apply RBAC tags, check for duplicates via content hash, then either process immediately (critical) or add to the webhook queue.

### Extension Points (20% Customization)

Each source can override four pluggable handlers for custom behavior — `AuthHandler` (verify signatures), `PayloadParser` (extract event data from non-standard payloads), `FieldTransformer` (map org-specific fields to `RawDocument`), and `RBACEngine` (apply org-specific team routing rules). These are configured per-org via YAML and database overrides without forking the core code.

### Webhook → Agent Routing

After queuing, a Celery task (`process_webhook_event`) looks up the appropriate source agent by name, constructs a `RawDocument` from the normalized event data and RBAC tags, invokes the agent with an `ingest_and_index` instruction, and retries with exponential backoff (up to 3 times, 60s apart) on failure.

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

| Phase | Sources | Key Features | Status |
|-------|---------|--------------|--------|
| **Phase 1** | Notion, Confluence, GitHub, Jira, PDF, URL | Base adapter pattern, RawDocument model, generic ingestion pipeline | ✅ Done |
| **Phase 1b (NEW)** | Jira (full), Confluence (full), Files (PDF/DOCX/CSV/XML/HTML/TXT) | Real-time webhooks, heading-split chunking, breadcrumb context, OCR fallback, file watcher | ✅ Done — `src/jira_agent/`, `src/confluence_agent/`, `src/file_agent/` |
| **Phase 2 (Next)** | Slack, logs, error traces, metrics | Event-driven ingestion, real-time alerting, RBAC for chat | 🔄 Design ready |
| **Phase 3** | Business data (sales, inventory, finance, supply chain) | ORM connectors, bulk sync, entity extraction for graph | 🔄 Extensible |
| **Phase 4** | Multimodal (OCR, images, scanned docs) | Vision model integration, document layout analysis | 🔄 PDF OCR partial |
| **Phase 5** | Knowledge graph materialization | Neo4j full implementation, graph-aware retrieval, cross-domain reasoning | ✅ Done — `graph_store/` (extractor.py uses Gemini 2.5 Pro; writer.py, reader.py, stream.py) |

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

The Beat scheduler runs periodic sync tasks: Slack incremental sync every 15 minutes (900s), GitHub incremental sync every hour (3600s), log polling every 5 minutes (300s), and metrics anomaly polling every 15 minutes (900s).

#### C. Web Scraping (`src/adapters/web_scraper.py`)

`WebScraperAdapter.fetch_url(url)` fetches a single URL and returns a `RawDocument` with extracted text, title, and metadata. `SitemapAdapter.fetch_all(base_url)` fetches `sitemap.xml`, crawls all listed URLs respecting rate limits, and returns a list of `RawDocument` instances. Both can be dispatched as Celery tasks (`scrape_url.delay(url)`, `scrape_sitemap.delay(base_url)`) and monitored via the Flower UI at `http://localhost:5555`.

#### D. Polling Adapters (`src/adapters/polling.py`)

`LogAggregatorAdapter.fetch_incremental(service, last_sync)` reads from a log file and returns `RawDocument` instances for `ERROR`/`WARN` entries, including level, trace ID, and stack trace. `MetricsAdapter`, `ErrorTraceAdapter`, and `BusinessDataAdapter` are placeholders for integration with Prometheus/Datadog, Sentry/Datadog APM, and Salesforce/NetSuite/ERP systems respectively.

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
| **Phase 2** | Celery tasks, webhooks, polling | ✅ Ready |
| **Phase 3** | Business data adapters (placeholder) | 🔄 Extensible |
| **Phase 4** | OCR integration, multimodal | 🔄 Extensible |
| **Phase 5** | KG materialization tasks | ✅ Done — `graph_store/` (writer.py Celery-compatible, reader.py traversal, stream.py WebSocket) |

---

*For detailed implementation guide, see: [WEBSCRAPING_CELERY_REDIS.md](../WEBSCRAPING_CELERY_REDIS.md)*

*Previous: [04_integrations_and_tech_stack.md](./04_integrations_and_tech_stack.md)*
*Reference: [01_problem_and_architecture.md](./01_problem_and_architecture.md) for Area 5 knowledge graph design*
