# Complete System Architecture

> **Document purpose:** System-wide architecture covering backend, frontend, database, deployment, and all component interactions. Read this to understand how all pieces fit together.

---

## Table of Contents

1. [High-Level System Diagram](#high-level-system-diagram)
2. [Backend Architecture (src/)](#backend-architecture-src)
3. [Frontend Architecture (frontend/)](#frontend-architecture-frontend)
4. [API Contract](#api-contract)
5. [Data Flow](#data-flow)
6. [Deployment Architecture](#deployment-architecture)

---

## High-Level System Diagram

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL DATA SOURCES                                │
│  ┌──────────┐ ┌────────────┐ ┌────────┐ ┌──────┐ ┌──────┐ ┌──────────────┐   │
│  │ Notion   │ │ Confluence │ │ GitHub │ │ Slack │ │ Jira  │ │URLs + Firecrawl│   │
│  └──────────┘ └────────────┘ └────────┘ └──────┘ └──────┘ └──────────────┘   │
└────────────────────┬───────────────────────────────────────────────────────────┘
                     │ (Webhooks + Polling)
                     ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                            BACKEND (Python/FastAPI)                            │
│  ┌────────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐   │
│  │  Data Ingestion │  │ RAG + Retrieval  │  │  Analytics & Intelligence   │   │
│  │  ├─ Adapters    │  │ ├─ Hybrid search │  │  ├─ Query events           │   │
│  │  ├─ Docling     │  │ ├─ BGE-M3        │  │  ├─ Knowledge graph        │   │
│  │  ├─ GLiNER PII  │  │ ├─ Qdrant        │  │  └─ Anomaly detection      │   │
│  │  └─ Chunking    │  │ └─ LLM agents    │  └──────────────────────────────┘   │
│  └────────────────┘  └──────────────────┘                                      │
│         ▲                      ▲                          ▲                     │
│         │                      │                          │                     │
│  ┌──────┴──────────────────────┴──────────────────────────┴────────────┐      │
│  │              FastAPI Backend (Uvicorn)                             │      │
│  │              ├─ /api/query/* (search + follow-up)                 │      │
│  │              ├─ /api/analytics/* (dashboards)                    │      │
│  │              ├─ /api/admin/* (data source management)            │      │
│  │              └─ /ws (WebSocket for real-time alerts)             │      │
│  └──────┬──────────────────────────────────────────────────────────┘      │
│         │                                                                   │
│  ┌──────▼────────────────────────────────────────────────────────┐        │
│  │     Data Layer (PostgreSQL, Qdrant, Neo4j, Redis, S3)         │        │
│  │  ├─ PostgreSQL: Metadata, RBAC, audit trails, queries        │        │
│  │  ├─ Qdrant: Vector embeddings (dense + sparse)              │        │
│  │  ├─ Neo4j: Knowledge graph (Service/Library/Incident/Team)  │        │
│  │  ├─ Redis: Cache, session state, pub/sub, task queues       │        │
│  │  └─ S3: PDFs, user uploads, exports                          │        │
│  └──────┬────────────────────────────────────────────────────────┘        │
└─────────┼────────────────────────────────────────────────────────────────────┘
          │
          │ (REST API + WebSocket)
          ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React/TypeScript)                             │
│  ┌───────────────────────┐  ┌──────────────────┐  ┌────────────────────────┐  │
│  │  Query Interface      │  │  Dashboards      │  │  Admin UI              │  │
│  │  ├─ Search box        │  │  ├─ Query trends │  │  ├─ Data source mgmt   │  │
│  │  ├─ Results display   │  │  ├─ Knowledge    │  │  ├─ User management    │  │
│  │  ├─ Citations         │  │  │   health      │  │  ├─ RBAC editor        │  │
│  │  ├─ Follow-ups        │  │  ├─ Dependencies │  │  ├─ API keys           │  │
│  │  └─ Knowledge graph   │  │  └─ Alerts       │  │  └─ System health      │  │
│  └───────────────────────┘  └──────────────────┘  └────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  Component Layer (shadcn/ui + Tailwind)                                 │  │
│  │  ├─ Query & Search components                                           │  │
│  │  ├─ Chart & data table components (Recharts, TanStack Table)           │  │
│  │  ├─ Knowledge graph visualizer (Force-Graph)                           │  │
│  │  ├─ Authentication flow (JWT)                                          │  │
│  │  └─ Real-time notifications (WebSocket)                               │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  State Management (TanStack Query + Zustand)                            │  │
│  │  ├─ Server state: Queries, analytics, user data (TanStack Query)      │  │
│  │  └─ Client state: UI state, theme, filters (Zustand)                  │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## Backend Architecture (src/) — Agent-Based Design

### Core Principle: Per-Source Agents

Rather than generic adapters flowing through a single pipeline, each data source is an **independent agent** with:
- Source-specific authentication & adapters
- Source-optimized chunking (preserves context like Confluence breadcrumbs, Jira comment threading)
- Independent Celery tasks (different polling cadences, priorities)
- Independent FastAPI routers (explicit webhooks like `/webhooks/jira`)
- Self-contained testing (`test_run.py` per agent)

This design ensures **scalability by source**, **operational clarity**, and **production-grade maintainability**.

### Directory Structure

> **Note:** The actual repo layout diverges from early plans. The implemented structure is below. `src/query_engine/` and `src/retrieval/` referenced in earlier design docs do not exist — that logic lives in `agent/`. Graph endpoints live in `graph_store/`, not `src/api/graph.py`.

```
agent/                          # LangGraph multi-agent query engine (IMPLEMENTED)
├── api.py                      # POST /agent/query — SSE streaming endpoint
├── graph.py                    # LangGraph build: planner → [doc_search|ticket_lookup|live_docs] → synthesiser → guardrail
├── models.py                   # KnowledgeGraphState, QueryInput, ExecutionPlan, AgentResult, RetrievedChunk
├── config.py                   # LLM + agent config
├── prompts.py                  # Prompt templates
├── agents/
│   ├── planner.py              # Breaks query into AgentTask list
│   ├── synthesiser.py          # Streams answer tokens from top chunks
│   ├── guardrail.py            # Validates answer against sources; sets escalate flag
│   └── _gemini.py              # Gemini client helper (used in planner/synthesiser)
└── tools/
    ├── doc_search.py           # Qdrant hybrid dense+sparse search
    ├── ticket_lookup.py        # Jira-specific retrieval
    ├── live_docs.py            # Firecrawl real-time doc fetching
    └── summariser.py           # Context compression before synthesis

graph_store/                    # Neo4j knowledge graph (IMPLEMENTED)
├── api.py                      # GET /graph/nodes, POST /graph/ingest, GET /graph/traverse
├── stream.py                   # WS /graph/stream — streams nodes+edges with 50ms delay
├── extractor.py                # Gemini 2.5 Pro entity+relationship extraction (4 types, whitelist rels)
├── writer.py                   # Async Neo4j MERGE upserts, index creation
├── reader.py                   # Cypher traversal: incident→service→library→chunks
├── models.py                   # ExtractedEntity, ExtractedRelationship, ExtractionResult
└── config.py                   # Neo4j connection settings

src/
├── agents_app.py               # Combined FastAPI app: all agent routers + Qdrant/Redis init
│
├── jira_agent/                 # JIRA ingestion agent (IMPLEMENTED)
│   ├── __init__.py
│   ├── config.py               # JiraAgentConfig — JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN,
│   │                           #   JIRA_PROJECT_KEYS (csv), JIRA_WEBHOOK_SECRET, TEAM_ID
│   ├── adapter.py              # JiraAdapter — fetch_issue, fetch_all (JQL), fetch_incremental
│   │                           #   Basic auth (base64 email:api_token), ADF text extraction
│   ├── chunker.py              # chunk_jira_issue → chunk 0: issue body, chunks 1..N: comments
│   │                           #   Preserves thread structure for relation extraction
│   ├── pipeline.py             # ingest_issue / ingest_project → chunk → PII mask → embed → Qdrant
│   │                           #   Returns entity graph nodes for real-time streaming
│   ├── tasks.py                # Celery: jira_process_issue (queue=critical), 
│   │                           #   jira_sync_project (queue=polling)
│   ├── router.py               # FastAPI: POST /webhooks/jira, POST /jira/sync/{project_key}
│   └── test_run.py             # Mock + real runthrough; works without credentials
│
├── confluence_agent/           # Confluence ingestion agent (IMPLEMENTED)
│   ├── __init__.py
│   ├── config.py               # ConfluenceAgentConfig — BASE_URL, TOKEN, EMAIL,
│   │                           #   CONFLUENCE_SPACES (csv), CONFLUENCE_WEBHOOK_SECRET, TEAM_ID
│   ├── adapter.py              # ConfluenceAdapter — fetch_page, fetch_space, fetch_incremental (CQL)
│   │                           #   REST v2 API with pagination
│   ├── chunker.py              # chunk_confluence_page — BeautifulSoup heading-split + breadcrumbs
│   │                           #   [Space > Ancestor > Page] prefix on every chunk; tables = 1 chunk each
│   │                           #   Preserves hierarchy for entity linking
│   ├── pipeline.py             # ingest_page / ingest_space → chunk → PII mask → embed → Qdrant
│   │                           #   Returns entity graph nodes
│   ├── tasks.py                # Celery: confluence_process_page (queue=critical), 
│   │                           #   confluence_sync_space (queue=polling),
│   │                           #   confluence_periodic_sync (beat, 60 min incremental sync)
│   ├── router.py               # FastAPI: POST /webhooks/confluence, POST /confluence/sync/{space_key}
│   │                           #   POST /confluence/search (for admin dashboard)
│   └── test_run.py             # Mock + real runthrough; works without credentials
│
├── file_agent/                 # File ingestion agent (IMPLEMENTED)
│   ├── __init__.py
│   ├── config.py               # FileAgentConfig — UPLOAD_DIR, MAX_FILE_SIZE, ALLOWED_TYPES
│   ├── adapter.py              # FileAdapter — handle PDFs, DOCX, PPTX, TXT
│   │                           #   Uses docling for multi-format parsing
│   ├── chunker.py              # chunk_file_document — respects document structure (sections, pages)
│   ├── pipeline.py             # ingest_file → chunk → PII mask → embed → Qdrant
│   ├── tasks.py                # Celery: file_process_upload (queue=critical)
│   ├── router.py               # FastAPI: POST /files/upload, GET /files/{file_id}
│   └── test_run.py
│
├── shared/                     # Shared utilities (used by all agents)
│   ├── __init__.py
│   ├── pii_masker.py           # GLiNER-based PII detection (local, zero egress)
│   ├── embedder.py             # BGE-M3 embeddings (local inference)
│   ├── qdrant_client.py        # Qdrant connection + upsert helpers
│   ├── entity_extractor.py     # Extract entities/relationships from chunks (used per-agent)
│   ├── models.py               # Pydantic models (RawDocument, ChunkedDocument, Entity, Graph)
│   └── config.py               # Shared config (QDRANT_URL, REDIS_URL, etc.)
│
├── retrieval/                  # T1, T2, T3 retrieval layers (shared across queries)
│   ├── __init__.py
│   ├── hybrid_search.py        # T1: Dense + Sparse (RRF fusion) — queries Qdrant
│   ├── reranker.py             # BGE-reranker-v2-m3 integration
│   ├── context_compressor.py   # Compress top-5 into LLM context
│   ├── cag_agent.py            # T2: Cache-Augmented Generation (recent syncs)
│   ├── live_doc_agent.py       # T3: Real-time doc fetching (Firecrawl)
│   └── models.py               # Pydantic models for retrieval
│
├── query_engine/               # Query execution (LangGraph-based)
│   ├── __init__.py
│   ├── generator_agent.py      # Generator LLM agent (creates answer from context)
│   ├── critic_agent.py         # Critic LLM agent (validates against sources)
│   ├── orchestrator.py         # LangGraph: routes query through retrieval → generation → validation
│   ├── streaming.py            # Stream answer chunks + citations + graph to frontend
│   └── models.py               # Pydantic models for query responses
│
├── redis/                      # Redis utilities (shared)
│   ├── __init__.py
│   ├── cache.py                # Caching layer (with TTL)
│   ├── queues.py               # Task queues (per-agent ingestion, webhook events)
│   ├── session_state.py        # Query session state
│   ├── locks.py                # Distributed locks (prevent concurrent agent syncs)
│   └── pubsub.py               # Pub/sub for real-time graph updates to frontend (query_id → node)
│
├── api/                        # FastAPI main app + shared endpoints
│   ├── __init__.py
│   ├── auth.py                 # POST /auth/login, /auth/logout, /auth/refresh
│   ├── query.py                # POST /api/query (streaming), /api/query/{id}/follow-up
│   ├── workspace.py            # GET/POST /api/workspace/queries, /saved
│   ├── admin.py                # GET /api/admin/agents (show all agent statuses)
│   └── graph.py                # GET /api/graph/entities, /api/graph/query/{query_id}
│
├── db/                         # Database models & utilities
│   ├── __init__.py
│   ├── models.py               # SQLAlchemy models (User, Query, Document, Entity, Graph)
│   ├── session.py              # Database session management
│   └── init_db.py              # Schema initialization
│
├── auth/                       # Authentication & authorization
│   ├── __init__.py
│   ├── jwt_handler.py          # JWT encode/decode, token refresh
│   ├── oauth.py                # OAuth2 + SSO integration (phase 2)
│   ├── rbac.py                 # Role-based access control decorator
│   ├── permissions.py          # Permission checks
│   └── models.py               # User, Role, Permission models
│
├── utils/                      # Shared utilities
│   ├── __init__.py
│   ├── logger.py               # Structured logging (JSON)
│   ├── metrics.py              # Prometheus metrics
│   ├── telemetry.py            # OpenTelemetry (phase 2)
│   └── exceptions.py           # Custom exceptions
│
└── tests/                      # Comprehensive test suite
    ├── __init__.py
    ├── agents/                 # Per-agent tests (JIRA, Confluence, File)
    ├── retrieval/              # Retrieval pipeline tests
    ├── query_engine/           # Query generation + validation tests
    ├── fixtures/               # Pytest fixtures (mock data)
    └── integration/            # End-to-end scenarios
```

### Key Backend Design Decisions

1. **Per-Source Agents:** Each source (Jira, Confluence, File) is an independent module with its own adapter, chunker, pipeline, and Celery tasks. This enables source-specific optimization and independent scaling.

2. **Source-Optimized Chunking:** 
   - Confluence: Preserves `[Space > Ancestor > Page]` hierarchy for entity linking
   - Jira: Preserves comment threading for relation extraction
   - File: Respects document structure (sections, pages)
   - Each source extracts its own entity relationships

3. **Independent Celery Scheduling:**
   - `jira_sync_project` → configurable interval (often 1 hour)
   - `confluence_periodic_sync` → beat scheduler (60 min incremental)
   - `file_process_upload` → immediate (queue=critical)
   - Each agent controls its own cadence

4. **PII Masking First:** GLiNER runs in `shared/pii_masker.py` — local, zero-egress, runs before Qdrant indexing.

5. **Entity Extraction Per-Agent:** Each pipeline returns a graph of entities + relationships (e.g., Jira: issue→linked_issue, Confluence: page→linked_page). Frontend streams these nodes as they're extracted.

6. **Real-Time Graph Streaming:** Via Redis pub/sub (`query_id → {nodes, edges}`) — frontend doesn't wait for full completion.

7. **Redis Everywhere:** Cache, queues, session state, distributed locks, and pub/sub all via Redis.

8. **Hybrid Retrieval (T1):** Dense (BGE-M3) + Sparse (BM25) via RRF — queries Qdrant.

---

## Frontend Architecture (frontend/)

### Directory Structure

```
frontend/
├── index.html                   # Entry HTML (Vite serves this)
├── vite.config.ts              # Vite build config
├── tsconfig.json               # TypeScript config
├── tailwind.config.ts          # Tailwind design tokens + dark mode
├── postcss.config.js           # PostCSS + Tailwind plugins
├── package.json                # Dependencies + scripts
├── .env.example                # Required environment variables
│
├── src/
│   ├── main.tsx                # React app entry point
│   ├── App.tsx                 # Root component + routing
│   │
│   ├── components/
│   │   ├── common/             # Reusable components
│   │   │   ├── Header.tsx      # Top nav bar
│   │   │   ├── Sidebar.tsx     # Left navigation
│   │   │   ├── Footer.tsx      # Footer
│   │   │   ├── Button.tsx      # Button variants (from shadcn)
│   │   │   ├── Input.tsx       # Text input (from shadcn)
│   │   │   ├── Card.tsx        # Card container
│   │   │   ├── Modal.tsx       # Modal/dialog
│   │   │   ├── Badge.tsx       # Status badges
│   │   │   ├── Tooltip.tsx     # Tooltips
│   │   │   ├── Toast.tsx       # Toast notifications
│   │   │   └── Loading.tsx     # Loading skeleton
│   │   │
│   │   ├── query/              # Query interface (Engineer primary)
│   │   │   ├── SearchBox.tsx   # Main search input (Cmd+K support)
│   │   │   ├── QueryModal.tsx  # Modal for new query
│   │   │   ├── QueryHistory.tsx # Query history panel
│   │   │   ├── SuggestedTopics.tsx # Related queries
│   │   │   └── QueryFeedback.tsx # Thumbs up/down
│   │   │
│   │   ├── results/            # Results display + knowledge graph
│   │   │   ├── ResultsPage.tsx # Main results container
│   │   │   ├── Answer.tsx      # Generated answer with citations
│   │   │   ├── Citations.tsx   # Cited source chunks
│   │   │   ├── FollowUp.tsx    # Follow-up prompt
│   │   │   ├── KnowledgeGraph.tsx # Knowledge graph visualization
│   │   │   ├── GraphNode.tsx   # Individual node component
│   │   │   ├── RelatedDocs.tsx # Related document snippets
│   │   │   └── ShareResults.tsx # Share/export options
│   │   │
│   │   ├── analytics/          # Dashboards (Manager primary)
│   │   │   ├── AnalyticsDashboard.tsx # Main analytics page
│   │   │   ├── QueryTrendChart.tsx # Line chart for query volume
│   │   │   ├── TopicsChart.tsx # Bar chart for topics
│   │   │   ├── SuccessRateGauge.tsx # Gauge chart
│   │   │   ├── KnowledgeHealthDashboard.tsx # Health metrics
│   │   │   ├── DependencyTracker.tsx # Breaking changes table
│   │   │   ├── EscalationTable.tsx # Unresolved queries
│   │   │   ├── TeamSettings.tsx # Team configuration
│   │   │   └── AnalyticsExport.tsx # Export reports
│   │   │
│   │   ├── admin/              # Admin UI (Admin primary)
│   │   │   ├── AdminDashboard.tsx # Main admin page
│   │   │   ├── SystemHealth.tsx # Health status cards
│   │   │   ├── DataSourceManager.tsx # Add/edit sources
│   │   │   ├── DataSourceForm.tsx # Source configuration wizard
│   │   │   ├── UserManager.tsx # User list + invite
│   │   │   ├── RBACEditor.tsx  # RBAC policy editor
│   │   │   ├── APIKeyManager.tsx # Generate/revoke keys
│   │   │   └── SystemLogs.tsx  # View logs + alerts
│   │   │
│   │   └── auth/               # Authentication UI
│   │       ├── LoginPage.tsx   # Login form (SSO + fallback)
│   │       ├── SSORedirect.tsx # OAuth callback handler
│   │       └── ProtectedRoute.tsx # Route guard
│   │
│   ├── pages/                  # Route pages (using TanStack Router)
│   │   ├── Home.tsx            # Dashboard home
│   │   ├── QueryPage.tsx       # Query results page
│   │   ├── AnalyticsPage.tsx   # Analytics dashboards
│   │   ├── AdminPage.tsx       # Admin dashboards
│   │   ├── WorkspacePage.tsx   # Personal/team workspace
│   │   ├── NotFoundPage.tsx    # 404 page
│   │   └── ErrorPage.tsx       # Error boundary
│   │
│   ├── hooks/                  # Custom React hooks
│   │   ├── useSSEStream.ts     # SSE consumer for POST /agent/query — manages fetch + ReadableStream parsing
│   │   ├── useGraphStream.ts   # WebSocket consumer for WS /graph/stream — feeds Force-Graph 2D progressively
│   │   ├── useNotifications.ts # WebSocket consumer for WS /ws system notifications (future)
│   │   ├── useAnalytics.ts     # Fetch analytics data
│   │   ├── useAuth.ts          # Authentication state
│   │   ├── useTheme.ts         # Dark mode toggle
│   │   ├── useLocalStorage.ts  # Persist state to localStorage
│   │   ├── usePagination.ts    # Pagination logic
│   │   └── useDebounce.ts      # Debounce search input
│   │
│   ├── stores/                 # Zustand state management
│   │   ├── authStore.ts        # User + auth state
│   │   ├── uiStore.ts          # UI state (theme, sidebar open, etc.)
│   │   ├── filterStore.ts      # Dashboard filters
│   │   └── workspaceStore.ts   # Workspace selections
│   │
│   ├── lib/
│   │   ├── api.ts              # TanStack Query setup + HTTP client
│   │   ├── http.ts             # httpx client wrapper (JWT refresh)
│   │   ├── auth.ts             # JWT helpers, localStorage auth
│   │   ├── websocket.ts        # WebSocket manager for alerts
│   │   ├── utils.ts            # General utilities (debounce, etc.)
│   │   ├── validators.ts       # Input validation (Zod)
│   │   ├── constants.ts        # App-wide constants
│   │   ├── error-handler.ts    # Centralized error handling
│   │   └── date.ts             # Date formatting helpers
│   │
│   ├── types/
│   │   ├── index.ts            # Re-export all types
│   │   ├── api.ts              # API response types
│   │   ├── user.ts             # User + auth types
│   │   ├── query.ts            # Query + results types
│   │   ├── analytics.ts        # Analytics types
│   │   ├── components.ts       # Component prop types
│   │   └── errors.ts           # Error types
│   │
│   ├── styles/
│   │   ├── globals.css         # Global styles + Tailwind imports
│   │   ├── design-tokens.css   # Design tokens (terracotta, white, dark mode)
│   │   ├── animations.css      # Custom animations (optional)
│   │   └── responsive.css      # Responsive utility classes
│   │
│   └── config/
│       ├── routes.ts           # TanStack Router configuration
│       ├── env.ts              # Environment variables + validation
│       └── queryClient.ts      # TanStack Query client config
│
├── public/                     # Static assets
│   ├── logo.svg                # Logo
│   ├── favicon.ico             # Favicon
│   └── assets/                 # Images, icons
│
├── tests/
│   ├── __mocks__/              # Mock data + API responses
│   ├── components/             # Component tests (Vitest + RTL)
│   ├── hooks/                  # Hook tests
│   ├── utils/                  # Utility tests
│   └── setup.ts                # Vitest + RTL setup
│
├── .eslintrc.json              # ESLint config
├── .prettierrc                 # Prettier config
└── README.md                   # Frontend development guide
```

### Frontend Design Decisions

1. **Vite + React 18:** Fast dev, instant HMR, minimal config. No SSR needed for SPA.
2. **TanStack Router:** Fully typed routing; better DX than React Router v6.
3. **TanStack Query:** Server state management with automatic caching/refetching.
4. **Zustand:** Lightweight client state (theme, UI, filters); no Redux boilerplate.
5. **shadcn/ui + Tailwind:** Copy-paste components, full control, design tokens system.
6. **Responsive Design:** Mobile (320px), Tablet (768px), Desktop (1024px+).
7. **WebSocket:** Native API for real-time alerts; no Socket.io overhead.
8. **JWT + httpOnly Cookies:** Secure auth; backend validates on every request.

---

## API Contract

### Authentication

```
POST /api/auth/login
├─ Request: { email, password } or { sso_provider, sso_token }
├─ Response: { access_token, refresh_token, user: { id, email, role, team_id } }
├─ Sets httpOnly cookie: __auth_token
└─ Bearer token in Authorization header for all subsequent requests

POST /api/auth/refresh
├─ Request: { refresh_token }
├─ Response: { access_token }
└─ Auto-called by frontend before token expires

POST /api/auth/logout
├─ Clears httpOnly cookie
└─ Backend invalidates refresh token in Redis
```

### Agent Webhook Endpoints (Per-Source)

```
POST /webhooks/jira
├─ Validates Jira webhook signature (X-Atlassian-Webhook-Signature)
├─ Extracts issue_created, issue_updated, comment_created events
├─ Routes to jira_process_issue Celery task (queue=critical)
└─ Returns immediately (202 Accepted)

POST /webhooks/confluence
├─ Validates Confluence webhook signature
├─ Extracts page_created, page_updated, page_trashed events
├─ Routes to confluence_process_page Celery task (queue=critical)
└─ Returns immediately (202 Accepted)

POST /files/upload
├─ Accepts multipart/form-data with file + team_id
├─ Routes to file_process_upload Celery task (queue=critical)
├─ Returns file_id immediately; processing async
└─ Frontend polls /files/{file_id} for status

POST /jira/sync/{project_key}
├─ Manual trigger; requires admin role
├─ Routes to jira_sync_project Celery task (queue=polling)
└─ Returns job_id for polling

POST /confluence/sync/{space_key}
├─ Manual trigger; requires admin role
├─ Routes to confluence_sync_space Celery task (queue=polling)
└─ Returns job_id for polling
```

### Query API (Streaming SSE)

```
POST /agent/query
├─ Request: { query: string, team_id: string, session_id: string }
├─ Response: Content-Type: text/event-stream
│  ├─ event: plan_ready        → { tasks: [AgentTask], reasoning: string }
│  ├─ event: agent_started     → { agent: "doc_search"|"ticket_lookup"|"live_docs"|"summariser" }
│  ├─ event: agent_done        → { agent: string, chunks: [RetrievedChunk], confidence: "high"|"medium"|"low" }
│  ├─ event: synthesis_started → {}
│  ├─ event: answer_chunk      → { chunk: string }   (repeats, one per token)
│  ├─ event: guardrail_result  → { score: float, escalate: bool }
│  ├─ event: done              → {}
│  └─ event: error             → { message: string }
└─ Headers: Cache-Control: no-cache, X-Accel-Buffering: no

POST /api/query/{query_id}/feedback
├─ Request: { sentiment: "helpful"|"not_helpful"|"hallucinated", text?: string }
└─ Response: { success: true }
```

### Knowledge Graph API

```
GET /graph/nodes?limit=50
└─ Response: { count: int, nodes: [{ label: string, name: string }] }
   (excludes Chunk and Document nodes — returns Service/Library/Incident/Team only)

POST /graph/ingest
├─ Request: { chunk_ids: [string], team_id: string }
└─ Response: { ingested: int }
   (fetches chunks from Supabase, runs Gemini extraction, upserts to Neo4j)

GET /graph/traverse?type=incident|service|library&name=string&team_id=string
└─ Response: { type, name, team_id, chunks: [string] }
   (multi-hop Cypher traversal — returns text chunks for context augmentation)

WS /graph/stream
└─ Streams: node events, edge events, then done event (see Real-Time API above)
```

### Analytics API

```
GET /api/analytics/queries?date_range=30d&team_id=...
├─ Response: {
│    query_count: 1243,
│    unique_users: 243,
│    avg_response_time_ms: 1200,
│    success_rate: 0.76,
│    trend: { data: [{date, count}] }
│  }

GET /api/analytics/knowledge-health
├─ Response: {
│    overall_score: 7.2,
│    coverage: 0.68,
│    freshness: 0.82,
│    accuracy: 0.76,
│    accessibility: 0.71,
│    gaps: [{ topic: "ORM patterns", queries: 12, solutions: 0 }]
│  }

GET /api/analytics/dependencies
├─ Response: {
│    dependencies: [{name, current_version, latest_version, breaking_changes}],
│    alerts: 3
│  }
```

### Admin API

```
POST /api/admin/sources
├─ Request: { type, config, rbac_level }
├─ Response: { id, status, test_result }
└─ Triggers background sync

GET /api/admin/sources
├─ Response: [{ id, type, status, last_sync, record_count }]

PATCH /api/admin/sources/{id}
├─ Request: { name, config, rbac_level }
├─ Response: { updated_source }

DELETE /api/admin/sources/{id}
├─ Soft delete; preserves audit trail

---

POST /api/admin/users/invite
├─ Request: { emails: ["alice@..."], role, team_id }
├─ Response: { invitations: [{ email, invitation_id, expires_at }] }
└─ Sends email invite

GET /api/admin/users
├─ Response: [{ id, email, role, team_id, status, created_at }]

DELETE /api/admin/users/{user_id}
├─ Deactivates user (no hard delete for compliance)

---

POST /api/admin/rbac
├─ Request: { name, description, teams, sources, filters }
├─ Response: { id, policy }
└─ Returns doc count matching policy

GET /api/admin/rbac
├─ Response: [{ id, name, doc_count }]

PATCH /api/admin/rbac/{id}
├─ Update existing policy

---

POST /api/admin/api-keys
├─ Request: { name, permissions, rate_limits, expiry }
├─ Response: { key: "sk_...", created_at }
└─ Only returned once

GET /api/admin/api-keys
├─ Response: [{ name, created_at, last_used, permissions }]
```

### Bash Development Testing

Use these instead of Swagger UI when you need to test streaming behaviour from the terminal.

**Test SSE query stream (replaces Swagger — Swagger can't stream SSE):**
```bash
#!/usr/bin/env bash
# test_query.sh — streams the SSE response token-by-token to stdout

BASE_URL="${GODSPEED_API:-http://localhost:8000}"

curl -N -s \
  -X POST "${BASE_URL}/agent/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the auth service?","team_id":"team-1","session_id":"test-001"}' \
| while IFS= read -r line; do
    echo "$line"
  done
```

**Test graph REST endpoints:**
```bash
BASE_URL="${GODSPEED_API:-http://localhost:8000}"

# List all graph nodes
curl -s "${BASE_URL}/graph/nodes?limit=20" | python3 -m json.tool

# Traverse from a service
curl -s "${BASE_URL}/graph/traverse?type=service&name=auth-service&team_id=team-1" \
  | python3 -m json.tool

# Ingest chunks into graph
curl -s -X POST "${BASE_URL}/graph/ingest" \
  -H "Content-Type: application/json" \
  -d '{"chunk_ids":["chunk-abc123"],"team_id":"team-1"}' \
  | python3 -m json.tool
```

**Test WebSocket graph stream (requires `wscat` — install with `npm i -g wscat`):**
```bash
BASE_URL="${GODSPEED_WS:-ws://localhost:8000}"
wscat -c "${BASE_URL}/graph/stream"
# Prints node/edge/done events as they arrive
```

**Test Jira webhook signature (bash + openssl):**
```bash
BASE_URL="${GODSPEED_API:-http://localhost:8000}"
BODY='{"webhookEvent":"jira:issue_created","issue":{"id":"TEST-1","fields":{"summary":"Auth service down"}}}'
SECRET="your_jira_webhook_secret"
SIG="sha256=$(echo -n "${BODY}" | openssl dgst -sha256 -hmac "${SECRET}" | awk '{print $2}')"

curl -s -X POST "${BASE_URL}/webhooks/jira" \
  -H "Content-Type: application/json" \
  -H "X-Atlassian-Webhook-Signature: ${SIG}" \
  -d "${BODY}"
```

**Test file upload:**
```bash
BASE_URL="${GODSPEED_API:-http://localhost:8000}"
curl -s -X POST "${BASE_URL}/files/upload" \
  -F "file=@/path/to/doc.pdf" \
  -F "team_id=team-1"
```

---

### Real-Time API

There are two distinct real-time channels — do not conflate them:

**Channel 1: Query streaming (SSE)**
```
POST /agent/query   →   Content-Type: text/event-stream

Emits events in order:
  event: plan_ready        data: { tasks: [...], reasoning: "..." }
  event: agent_started     data: { agent: "doc_search" }
  event: agent_done        data: { agent: "doc_search", chunks: [...], confidence: "high" }
  event: synthesis_started data: {}
  event: answer_chunk      data: { chunk: "token text" }   ← repeats per token
  event: guardrail_result  data: { score: 0.92, escalate: false }
  event: done              data: {}
  event: error             data: { message: "..." }        ← on failure

Request body: { query: string, team_id: string, session_id: string }
```

**Channel 2: Knowledge graph visualization (WebSocket)**
```
WS /graph/stream

Emits in order (50ms delay between each):
  { event: "node", id: "...", label: "Service", name: "auth-service" }
  { event: "edge", from: "...", to: "...", rel: "DEPENDS_ON" }
  ...
  { event: "done", nodes_count: 42, edges_count: 87 }
```

**Channel 3: System notifications (WebSocket)**
```
WS /ws   (future — not yet implemented)

Will emit:
  event: "query_answered"  → { query_id, new_docs_count }
  event: "escalation_spike" → { topic, spike_rate }         (manager-only)
  event: "breaking_change"  → { dependency, version, url }  (admin-only)
  event: "data_sync_failed" → { source, error }             (admin-only)
  event: "knowledge_gap"    → { topic, query_count }        (all users)
```

---

## Data Flow

### Flow 1: Engineer Query → Answer

```
1. Engineer types query in SearchBox
   ├─ frontend sends POST /agent/query { query, team_id, session_id }
   └─ frontend simultaneously opens WS /graph/stream for parallel graph rendering

2. Backend receives query via SSE stream
   ├─ LangGraph planner breaks query into AgentTask list → emits plan_ready
   ├─ Each agent runs (doc_search / ticket_lookup / live_docs) → emits agent_started + agent_done
   ├─ doc_search: BGE-M3 embed → Qdrant hybrid search (dense+sparse RRF) → top 50 → BGE reranker → top 5
   ├─ Synthesiser streams answer tokens → emits answer_chunk per token
   └─ Guardrail validates answer against source chunks → emits guardrail_result

3. Guardrail result
   ├─ guardrail_passed=true → done event
   ├─ guardrail_passed=false + escalate=true → warning banner shown in frontend
   └─ Citations come from agent_done chunks (already streamed in step 2)

4. Frontend connects to graph stream (parallel to query SSE)
   ├─ WS /graph/stream streams the pre-built Neo4j graph (query-scoped subgraph)
   ├─ Nodes arrive one-by-one with 50ms delays: { event:"node", label, name }
   ├─ Edges arrive after nodes: { event:"edge", from, to, rel }
   └─ { event:"done" } signals completion
   Note: The knowledge graph is pre-built at ingestion time by Gemini 2.5 Pro
   (graph_store/extractor.py), not extracted from the answer at query time.

5. Frontend receives stream
   ├─ Displays answer immediately (no waiting)
   ├─ Renders citations as they arrive
   ├─ Knowledge graph appears once first connection established
   ├─ Related docs populate as backend fetches
   └─ Full page interactive once final "done" event received

6. Feedback recorded
   ├─ Engineer clicks thumbs up/down
   ├─ Frontend POSTs /api/query/{id}/feedback
   ├─ Backend records sentiment + triggers analytics update
   └─ Feedback visible in query history + aggregated for managers
```

### Flow 2: Data Ingestion (Daily/Polling)

```
1. Ingestion task triggered
   ├─ Webhook from source (e.g., Notion) OR Celery periodic task

2. Fetch stage
   ├─ Adapter queries source API
   ├─ Detects new/updated items (via timestamps or ETags)
   ├─ Downloads content

3. Normalize stage (Docling)
   ├─ Converts PDF/HTML/markdown to clean markdown
   ├─ Extracts tables as markdown tables
   ├─ Detects code blocks + language

4. PII Mask stage (GLiNER, local)
   ├─ Scans text for PII (names, emails, IDs, etc.)
   ├─ Replaces PII with placeholders (e.g., [REDACTED_EMAIL])
   ├─ Logs redaction for audit trail

5. Chunk stage (Semantic)
   ├─ Splits by paragraph/sentence boundaries
   ├─ Never splits code blocks or lists
   ├─ 15% overlap between chunks
   ├─ 256–512 tokens per chunk

6. Tag stage (Metadata)
   ├─ Adds source_uri, source_type, ingested_at
   ├─ Adds RBAC tag (public / team / restricted)
   ├─ Computes content_hash (for change detection)
   ├─ Detects doc_type (SOP, API doc, PR, etc.)

7. Embed stage
   ├─ Sends chunks to BGE-M3
   ├─ Gets 384-dim dense vectors
   ├─ Extracts sparse BM25-like vectors

8. Index stage
   ├─ Uploads dense vectors to Qdrant HNSW index
   ├─ Uploads sparse vectors to Qdrant sparse index
   ├─ Upserts metadata (PostgreSQL)
   ├─ Updates Redis cache (last_sync_timestamp)

9. Complete
   ├─ Backend records sync success in PostgreSQL
   ├─ Triggers webhook for frontend real-time update
   └─ Notifies admins if errors
```

### Flow 3: Manager Views Analytics

```
1. Manager navigates to /analytics

2. Frontend loads analytics data
   ├─ POST /api/analytics/queries?date_range=30d
   ├─ POST /api/analytics/knowledge-health
   ├─ POST /api/analytics/dependencies

3. Backend aggregates from event logs
   ├─ Queries PostgreSQL (query_events table)
   ├─ Aggregates by date, team, topic
   ├─ Computes trends, success rates
   ├─ Identifies gaps from failed queries

4. Frontend renders dashboards
   ├─ Query trends (Recharts line chart)
   ├─ Topics (bar chart)
   ├─ Success rate (gauge)
   ├─ Escalations table
   ├─ Knowledge health heatmap

5. Optional: Manager exports report
   ├─ Frontend POSTs /api/analytics/export?format=pdf
   ├─ Backend generates PDF via ReportLab
   ├─ Streams PDF download to browser
```

---

## Deployment Architecture

### Development (docker-compose)

```yaml
services:
  postgres:
    image: postgres:15
    volumes: [./data/postgres:/var/lib/postgresql/data]
    ports: [5432:5432]

  redis:
    image: redis:7-alpine
    ports: [6379:6379]

  qdrant:
    image: qdrant/qdrant:latest
    volumes: [./data/qdrant:/qdrant/storage]
    ports: [6333:6333]

  backend:
    build: ./backend
    ports: [8000:8000]
    depends_on: [postgres, redis, qdrant]
    environment:
      SQLALCHEMY_DATABASE_URL: postgresql://user:pass@postgres:5432/godspeed
      REDIS_URL: redis://redis:6379
      QDRANT_URL: http://qdrant:6333

  frontend:
    build: ./frontend
    ports: [3000:3000]
    depends_on: [backend]
    environment:
      VITE_API_BASE_URL: http://localhost:8000

  neo4j:
    image: neo4j:5
    ports: ["7474:7474", "7687:7687"]
    volumes: [./data/neo4j:/data]
    environment:
      NEO4J_AUTH: neo4j/godspeed_dev
      NEO4J_PLUGINS: '["apoc"]'

  celery:
    build: ./backend
    command: celery -A src.celery_app worker -Q critical,default,polling -l info
    depends_on: [postgres, redis, qdrant, neo4j]
    environment:
      SQLALCHEMY_DATABASE_URL: postgresql://user:pass@postgres:5432/godspeed
      REDIS_URL: redis://redis:6379
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USERNAME: neo4j
      NEO4J_PASSWORD: godspeed_dev
```

### Production (Kubernetes)

```yaml
# Deployments
- backend (FastAPI, 3 replicas, HPA)
- frontend (Nginx, 2 replicas, CDN)
- celery-worker (5 replicas, autoscaling on queue depth)

# StatefulSets
- postgres (with backup via S3)
- redis (cluster mode)
- qdrant (with persistence)

# Services
- backend-svc (ClusterIP)
- frontend-svc (LoadBalancer)
- postgres-svc (ClusterIP)
- redis-svc (ClusterIP)
- qdrant-svc (ClusterIP)

# ConfigMaps & Secrets
- app-config (env vars)
- api-keys (AWS S3, Notion OAuth, etc.)
- tls-certs (HTTPS)

# Ingress
- Routes /api/* to backend
- Routes /* to frontend
- TLS termination
```

### Self-Hosted (Single Server)

```
nginx (reverse proxy, static frontend)
  ├─ localhost:8000 (FastAPI backend)
  ├─ localhost:5432 (PostgreSQL)
  ├─ localhost:6379 (Redis)
  └─ localhost:6333 (Qdrant)

All services in systemd or Docker containers
Automated backups via Cron + S3
Monitoring via Prometheus + Grafana (optional)
```

---

## Key Architectural Principles

1. **Separation of Concerns:** Each layer (adapter, ingestion, retrieval, agent, API) has one responsibility.
2. **Stateless Backend:** FastAPI scales horizontally; state lives in PostgreSQL/Redis.
3. **Async Everywhere:** Celery for long-running tasks; FastAPI with asyncio for I/O.
4. **RBAC First:** All queries filtered by user's team/permissions at retrieval time.
5. **Streaming Results:** Don't wait for complete answer; stream chunks to frontend progressively.
6. **Local PII:** GLiNER runs on-premises; zero data egress for compliance.
7. **Cacheable at Every Layer:** Embeddings cached, searches cached, answers cached (with refresh policy).
8. **Observable:** Structured logging, metrics, traces (OpenTelemetry phase 2).

