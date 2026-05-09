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
│  │         Data Layer (PostgreSQL, Qdrant, Redis, S3)            │        │
│  │  ├─ PostgreSQL: Metadata, RBAC, audit trails, queries        │        │
│  │  ├─ Qdrant: Vector embeddings (dense + sparse)              │        │
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

## Backend Architecture (src/)

### Directory Structure

```
src/
├── main.py                      # FastAPI app entry point, CORS, middleware setup
├── config.py                    # Environment config, settings, secrets
├── celery_app.py                # Celery app init, task discovery
│
├── adapters/                    # ALL data source adapters (pluggable)
│   ├── __init__.py             # Registry + factory (dynamic adapter loading)
│   ├── base.py                 # BaseSourceAdapter interface
│   │   └── Methods: authenticate(), list_items(), get_item(), sync()
│   ├── notion.py               # NotionAdapter
│   ├── confluence.py           # ConfluenceAdapter
│   ├── github.py               # GitHubAdapter
│   ├── slack.py                # SlackAdapter
│   ├── jira.py                 # JiraAdapter
│   ├── pdf.py                  # PDFAdapter (file upload)
│   ├── url_fetcher.py          # URLAdapter (Firecrawl + BeautifulSoup)
│   ├── logs.py                 # LogAggregatorAdapter
│   ├── metrics.py              # MetricsAdapter
│   ├── error_traces.py         # ErrorTraceAdapter
│   ├── business_data.py        # BusinessDataAdapter
│   └── ocr.py                  # OCRAdapter
│
├── integrations/               # Webhooks, event handlers, polling tasks
│   ├── __init__.py
│   ├── webhooks.py             # Generic webhook router
│   ├── notion/
│   │   ├── webhooks.py         # Notion webhook handler
│   │   └── tasks.py            # Notion polling tasks (Celery)
│   ├── confluence/
│   │   └── tasks.py            # Confluence polling sync
│   ├── github/
│   │   ├── webhooks.py         # GitHub webhook handler
│   │   └── tasks.py            # GitHub polling tasks
│   ├── slack/
│   │   ├── webhooks.py         # Slack event subscriptions
│   │   └── tasks.py            # Slack message indexing
│   ├── jira/
│   │   ├── webhooks.py         # Jira webhook handler
│   │   └── tasks.py            # Jira issue sync
│   ├── logs/
│   │   ├── webhooks.py         # Error log ingestion
│   │   └── tasks.py            # Log polling
│   ├── metrics/
│   │   └── tasks.py            # Metrics collection
│   └── business_data/
│       └── tasks.py            # ERP data sync
│
├── orm/                        # Database adapters (for ERP/CRM sources)
│   ├── __init__.py
│   ├── base.py                 # BaseORM interface
│   ├── postgres.py             # PostgreSQL queries
│   ├── salesforce.py           # Salesforce REST API
│   ├── netsuite.py             # NetSuite SuiteTalk API
│   ├── sap.py                  # SAP OData API
│   └── generic_rest.py         # Generic REST API wrapper
│
├── ingestion/                  # Data processing pipeline (multi-stage)
│   ├── __init__.py
│   ├── orchestrator.py         # Routes docs through pipeline stages
│   ├── fetcher.py              # Stage 1: FETCH from sources
│   ├── normalizer.py           # Stage 2: CLEAN & NORMALISE (Docling)
│   ├── pii_masker.py           # Stage 3: PII MASKING (GLiNER, local)
│   ├── chunker.py              # Stage 4: SEMANTIC CHUNKING
│   ├── tagger.py               # Stage 5: METADATA TAGGING
│   ├── embedder.py             # Embed chunks (BGE-M3)
│   ├── indexer.py              # Index to Qdrant (dense + sparse)
│   └── models.py               # Pydantic models for ingestion
│
├── retrieval/                  # T1, T2, T3 retrieval layers
│   ├── __init__.py
│   ├── hybrid_search.py        # T1: Dense + Sparse (RRF fusion)
│   ├── reranker.py             # BGE-reranker-v2-m3 integration
│   ├── context_compressor.py   # Compress top-5 into LLM context
│   ├── cag_agent.py            # T2: Cache-Augmented Generation
│   ├── live_doc_agent.py       # T3: Real-time doc fetching (Firecrawl)
│   └── models.py               # Pydantic models for retrieval
│
├── agents/                     # LangGraph agents (multi-agent orchestration)
│   ├── __init__.py
│   ├── base.py                 # BaseAgent interface
│   ├── generator_agent.py      # Generator (creates answer)
│   ├── critic_agent.py         # Critic (validates answer)
│   ├── ingestion_agent.py      # Ingestion orchestrator
│   ├── entity_extractor_agent.py # Extracts entities for knowledge graph
│   ├── anomaly_detector_agent.py # Detects query anomalies
│   └── graph_builder.py        # Constructs LangGraph stateful workflow
│
├── redis/                      # Redis utilities (caching, queues, state)
│   ├── __init__.py
│   ├── cache.py                # Caching layer (with TTL)
│   ├── queues.py               # Task queues (ingest, webhook, low-priority)
│   ├── session_state.py        # Session state management
│   ├── locks.py                # Distributed locks (prevents race conditions)
│   └── pubsub.py               # Pub/sub for real-time updates
│
├── tasks/                      # Celery task definitions (background jobs)
│   ├── __init__.py
│   ├── ingestion_tasks.py      # Main ingest orchestration
│   ├── sync_tasks.py           # Periodic polling tasks (incremental syncs)
│   ├── webhook_tasks.py        # Handle webhook queuing
│   ├── validation_tasks.py     # Generator + Critic validation
│   ├── analytics_tasks.py      # Aggregate analytics (nightly jobs)
│   ├── dependency_tasks.py     # Check for breaking changes
│   └── cleanup_tasks.py        # Maintenance (cache expiry, log rotation)
│
├── api/                        # REST API endpoints
│   ├── __init__.py
│   ├── auth.py                 # POST /auth/login, /auth/logout, /auth/refresh
│   ├── query.py                # POST /query (main search), /follow-up
│   ├── analytics.py            # GET /analytics/queries, /health, /trends
│   ├── admin.py                # POST/GET /admin/sources, /users, /rbac
│   ├── workspace.py            # GET/POST /workspace/queries, /saved
│   └── dependencies.py         # GET /dependencies/
│
├── db/                         # Database models & utilities
│   ├── __init__.py
│   ├── models.py               # SQLAlchemy models (User, Query, Document, etc.)
│   ├── session.py              # Database session management
│   ├── migrations/             # Alembic migrations (if using)
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
│   ├── cache_utils.py          # Cache helpers (with decorator)
│   ├── validators.py           # Input validation helpers
│   └── exceptions.py           # Custom exceptions
│
├── ml/                         # ML model integration (inference only)
│   ├── __init__.py
│   ├── embedder.py             # BGE-M3 embeddings (HuggingFace)
│   ├── reranker.py             # BGE-reranker-v2-m3
│   ├── pii_detector.py         # GLiNER for PII
│   ├── entity_extractor.py     # Entity/relation extraction
│   └── models_config.py        # Model paths, device selection (CPU/GPU)
│
└── tests/                      # Comprehensive test suite
    ├── __init__.py
    ├── test_adapters.py        # Unit tests for adapters
    ├── test_retrieval.py       # Unit tests for retrieval
    ├── test_agents.py          # Integration tests for agents
    ├── test_api.py             # API endpoint tests
    ├── fixtures/               # Pytest fixtures (mock data)
    └── integration/            # End-to-end test scenarios
```

### Key Backend Design Decisions

1. **Adapter Pattern:** All data sources implement `BaseSourceAdapter`. New sources can be added without modifying core logic.
2. **Multi-Stage Ingestion:** 5-stage pipeline ensures consistent quality (fetch → clean → mask → chunk → tag).
3. **PII Masking First:** GLiNER runs locally before ANY data hits the vector store (GDPR/HIPAA compliant).
4. **Hybrid Retrieval (T1):** Dense embeddings (BGE-M3) + Sparse indexing (BM25) fused via RRF for recall.
5. **LangGraph Orchestration:** Stateful multi-agent workflow for Generator + Critic validation.
6. **Redis Everywhere:** Cache, queues, session state, distributed locks, and pub/sub all via Redis.
7. **Celery for Async:** Background ingestion, polling, webhooks, and maintenance tasks.

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
│   │   ├── useQuery.ts         # Query search hook
│   │   ├── useAnalytics.ts     # Fetch analytics data
│   │   ├── useAuth.ts          # Authentication state
│   │   ├── useWebSocket.ts     # Real-time alerts
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

### Query API

```
POST /api/query
├─ Request: { question, conversation_id?, filters?: { team_id, source_type } }
├─ Response (Streaming): 
│  ├─ event: "answer_started" → { id, timestamp }
│  ├─ event: "answer_chunk" → { content } (streamed answer)
│  ├─ event: "citations" → { sources: [{ title, url, score, chunk }] }
│  ├─ event: "knowledge_graph" → { nodes, edges } (loads dynamically)
│  ├─ event: "related_docs" → { documents: [...] }
│  └─ event: "done" → { success: true }
└─ On error: { success: false, error: "...", code: 400|500 }

POST /api/query/{query_id}/follow-up
├─ Request: { follow_up_question }
├─ Response: (same streaming format)
└─ Appends to conversation history

POST /api/query/{query_id}/feedback
├─ Request: { sentiment: "helpful"|"not_helpful", text?: "..." }
├─ Response: { success: true }
└─ Records feedback for analytics
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

### Real-Time API (WebSocket)

```
ws://backend/ws

Connected client receives:
├─ event: "query_answered" → { query_id, new_docs_count } (when past query has new answers)
├─ event: "escalation_spike" → { topic, spike_rate } (manager-only)
├─ event: "breaking_change" → { dependency, version, url } (admin-only)
├─ event: "data_sync_failed" → { source, error } (admin-only)
└─ event: "knowledge_gap" → { topic, query_count } (all users)
```

---

## Data Flow

### Flow 1: Engineer Query → Answer

```
1. Engineer types query in SearchBox
   ├─ frontend sends POST /api/query

2. Backend receives query
   ├─ Validates RBAC (which docs can user access?)
   ├─ Generates embedding via BGE-M3
   ├─ Hybrid search: Dense (HNSW) + Sparse (BM25) → RRF → Top 50
   ├─ Re-ranks Top 50 → Top 5 via BGE-reranker-v2-m3
   ├─ Compresses 5 chunks → fits in LLM context
   └─ Streams answer chunks to frontend (event: "answer_chunk")

3. Backend validates answer
   ├─ Generator Agent created answer
   ├─ Critic Agent validates against sources
   ├─ If hallucination detected → warning banner
   └─ Streams citations (event: "citations")

4. Backend extracts entities + builds knowledge graph
   ├─ GLiNER extracts entities from answer
   ├─ Queries Qdrant for related entities
   ├─ Streams graph nodes/edges as they connect
   └─ Event: "knowledge_graph" with { nodes, edges }

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

  celery:
    build: ./backend
    command: celery -A celery_app worker -l info
    depends_on: [postgres, redis, qdrant]
    environment:
      SQLALCHEMY_DATABASE_URL: postgresql://user:pass@postgres:5432/godspeed
      REDIS_URL: redis://redis:6379
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

