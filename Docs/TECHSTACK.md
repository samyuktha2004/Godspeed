# Technical Stack

> **Document purpose:** Complete tech stack decisions for backend, frontend, infrastructure, and deployment. Rationale for each choice included.

---

## Table of Contents

1. [Backend Stack](#backend-stack)
2. [Frontend Stack](#frontend-stack)
3. [Infrastructure & DevOps](#infrastructure--devops)
4. [Data Storage & Retrieval](#data-storage--retrieval)
5. [ML / NLP Components](#ml--nlp-components)
6. [Deployment Targets](#deployment-targets)

---

## Backend Stack

### Core Runtime & API Framework

| Component | Technology | Rationale | Version |
|---|---|---|---|
| **Runtime** | Python 3.11+ | Standard for ML/data pipelines; excellent async support (asyncio); rich data science ecosystem | 3.11+ |
| **API Framework** | FastAPI + Uvicorn | Native async, automatic OpenAPI docs, built-in dependency injection, <100ms request overhead | 0.104+ |
| **Async Task Queue** | Celery + Redis broker | Battle-tested for background jobs; Redis for pub/sub and state; supports task retries and rate limiting | Celery 5.3+ |
| **HTTP Client** | httpx | Async-first, mirrors requests API; used for external doc fetching (Firecrawl, Tavily) | 0.25+ |
| **Type Hints** | Pydantic v2 | Runtime validation, JSON schema generation, strong typing for API contracts | 2.5+ |

### Data Processing & Ingestion

| Component | Technology | Rationale | Purpose |
|---|---|---|---|
| **Document Parsing** | Docling | Handles multi-format docs (PDF, HTML, markdown); preserves tables and code blocks | PDF/HTML/markdown normalization |
| **PII Detection** | GLiNER (local) | Zero egress; runs on-device; detects names, emails, IDs, addresses; GDPR/DPDP compliant | Pre-ingestion masking |
| **Chunking** | Custom semantic chunker (src/ingestion/) | Respects paragraph/code block boundaries; 15% overlap; prevents mid-function splits | Semantic chunking |
| **Embedding Model** | BGE-M3 (BAAI) | Multilingual dense + sparse in one pass; 8,192 token context; 384-dim output | Dense embeddings |
| **Reranker** | BGE-reranker-v2-m3 | Reranks top 50 to top 5; multilingual; efficient | Re-ranking after fusion |

### Vector Store & Semantic Search

| Component | Technology | Rationale | Notes |
|---|---|---|---|
| **Vector Database** | Qdrant (self-hosted or cloud) | Horizontal scalable; batch upload API; RBAC support; integrated sparse vector index (Rust backend) | Production-grade RAG |
| **Sparse Indexing** | Qdrant's native sparse index | BM25-equivalent without separate Elasticsearch; reduces infrastructure |  Hybrid search |
| **Full-Text Search** | Qdrant sparse vectors + RRF | Reciprocal Rank Fusion merges dense + sparse scores; deterministic, no tuning needed | Hybrid RAG |

### Agentic System & Orchestration

| Component | Technology | Rationale | Purpose |
|---|---|---|---|
| **Agent Framework** | LangGraph | Stateful graph execution; explicit node definitions; ReAct pattern built-in | Multi-agent coordination |
| **LLM Integration** | LangChain + model-agnostic design | Unified interface for Claude (primary), OpenAI fallback, local Ollama support | Generator + Critic agents |
| **Primary LLM** | Claude 3.5 Sonnet (Anthropic) | Best reasoning quality for validation; low hallucination rates (Stanford 2025 benchmark) | Generator + Critic |
| **Secondary LLM** | Claude 3 Haiku | Cheap, fast inference for light tasks (summarization, classification) | CAG, categorization |
| **Local LLM Fallback** | Ollama + Mistral-7B | For air-gapped deployments; lower quality but zero API dependency | HIPAA/FedRAMP compliance |

### Data Storage

| Component | Technology | Rationale | Purpose |
|---|---|---|---|
| **Primary DB** | PostgreSQL 15+ | ACID guarantees; full-text search via pg_trgm; JSON support; RBAC audit tables | Metadata, audit trails, RBAC |
| **Cache Layer** | Redis (self-hosted or Upstash) | Sub-millisecond reads; sorted sets for leaderboards; pub/sub for real-time notifications | Session state, caching |
| **Document Storage** | S3-compatible (AWS S3 or MinIO) | Durable long-term storage for PDFs, uploaded files, exports | PDFs, user uploads |
| **Time-Series DB** (Phase 2) | TimescaleDB (PostgreSQL extension) | Query volume trends, latency metrics, user activity patterns; built on PostgreSQL | Analytics time-series |

### Integrations & Connectors

| Component | Technology | Rationale | Purpose |
|---|---|---|---|
| **Notion** | notion-sdk-py | Official SDK; handles pagination, auth refresh | Notion workspace sync |
| **Confluence** | atlassian-python-api | Community-maintained; REST v2 support | Confluence space sync |
| **GitHub** | PyGithub | Community standard; handles GraphQL fallback; rate limit management | GitHub repo + PR sync |
| **Slack** | slack-sdk | Official SDK; event subscriptions, bolt framework for webhooks | Slack DM queries, alerts |
| **Jira** | atlassian-python-api | Same maintainer as Confluence; REST v3 | Jira issue sync |
| **External Docs** | Firecrawl (primary) + BeautifulSoup4 (fallback) | Firecrawl handles JS-rendered SPAs; BS4 fallback for static sites | Live doc fetching |
| **Web Search** | Tavily API | Specialized for RAG; better results than Google for documentation | Web search fallback |

### Development & Testing

| Component | Technology | Rationale | Purpose |
|---|---|---|---|
| **Testing Framework** | pytest + pytest-asyncio | De-facto standard; strong fixture support; async test support | Unit + integration tests |
| **Test Coverage** | Coverage.py | Track line and branch coverage; integrates with pytest | Coverage reporting |
| **Linting** | Ruff | Ultra-fast (Rust-based); replaces flake8 + isort | Code quality |
| **Type Checking** | pyright | Strict mode by default; catches more errors than mypy | Type safety |
| **Code Formatting** | Black | Deterministic; removes style debates | Code style |

---

## Frontend Stack

### Core Framework & Build

| Component | Technology | Rationale | Version |
|---|---|---|---|
| **Framework** | React 18 + TypeScript | Component-driven; strong typing; ecosystem; learning curve justified by team size | 18.2+ |
| **Build Tool** | Vite | 10x faster dev startup than webpack; near-instant HMR; minimal config | 5.0+ |
| **Type Safety** | TypeScript 5 | End-to-end type safety; integrates with Vite; strict mode enforced | 5.3+ |
| **Routing** | TanStack Router | Fully typed routing; nested routes; TypeScript-first; smaller bundle than React Router v6 | 1.28+ |
| **HTTP Client** | TanStack Query (React Query) | Server state management; automatic caching/invalidation; background refetching | 5.28+ |
| **Client State** | Zustand | Lightweight; no boilerplate; TypeScript-first; DevTools support | 4.4+ |
| **Forms** | React Hook Form + Zod | Minimal re-renders; schema-driven validation; TypeScript support; integrates with shadcn | 7.0+ / 3.22+ |

### UI Components & Styling

| Component | Technology | Rationale | Purpose |
|---|---|---|---|
| **Component Library** | shadcn/ui (Radix primitives) | Unstyled accessibility-first primitives; copy-paste model (full control); Tailwind-based | UI components |
| **Styling** | Tailwind CSS 3 | Utility-first; design tokens system; dark mode support; minimal CSS bloat | Styling system |
| **Design Tokens** | Tailwind config + CSS variables | Terracotta/White primary palette; dark mode support; custom spacing/colors | Design consistency |
| **Icons** | Lucide React | 1,500+ modern icons; tree-shakeable; TypeScript support | Icon set |
| **Animations** | Framer Motion (opt-in) | Smooth transitions where needed; not required for MVP; zero-config for basics | Micro-interactions |

### Data Visualization & Tables

| Component | Technology | Rationale | Purpose |
|---|---|---|---|
| **Charts** | Recharts | React-first; responsive; TypeScript support; integrates well with Tailwind | Query analytics graphs |
| **Data Tables** | TanStack React Table (headless) | Headless table library; sorting/filtering/pagination built-in; zero styling opinions; composable | Query history, data tables |
| **Real-Time Graph** | Force-Graph 2D (canvas-based) | WebGL rendering; 100k+ nodes performant; knowledge graph visualization | Knowledge graph display |
| **Time-Series** | Recharts (LineChart) | Sufficient for phase 1; can swap to Apache ECharts if needed | Query volume trends |

### Authentication & Security

| Component | Technology | Rationale | Purpose |
|---|---|---|---|
| **Auth Flow** | JWT + refresh tokens (backend-issued) | Stateless; supports mobile/SPA; backend validates on each request | User authentication |
| **Storage** | httpOnly cookies (primary) + sessionStorage fallback | Protects against XSS (httpOnly); CORS-aware | Token storage |
| **RBAC Enforcement** | Client-side + backend validation | Client-side for UX (show/hide features); backend for security (always validate) | Role-based access |
| **HTTPS** | TLS 1.3+ | Enforced in production; self-signed in dev (certbot for self-hosted) | Transport security |

### Real-Time Communication

| Component | Technology | Rationale | Purpose |
|---|---|---|---|
| **WebSocket Client** | Native WebSocket API (no Socket.io for MVP) | Simpler, lower latency; backend controls connection lifecycle | Real-time alerts/notifications |
| **Message Format** | JSON over WebSocket | Consistent with HTTP API; easy debugging; browser-native JSON.parse | Real-time updates |
| **Reconnection** | Exponential backoff (client-side) | Handles network hiccups; prevents thundering herd on backend | Connection resilience |

### Build & Development

| Component | Technology | Rationale | Purpose |
|---|---|---|---|
| **Package Manager** | pnpm | Faster than npm; lower disk usage; monorepo-friendly | Dependency management |
| **Linting** | ESLint + @typescript-eslint | Enforce code quality; catch common mistakes; TypeScript-aware | Code quality |
| **Formatting** | Prettier | Opinionated; removes style debates; integrates with ESLint | Code formatting |
| **Testing** | Vitest + React Testing Library | Vitest is Vite-native (instant); RTL tests real behavior, not implementation | Unit + integration tests |
| **E2E Testing** | Playwright | No JavaScript setup required; cross-browser; fast; integrates with CI | End-to-end tests |
| **Environment Management** | .env.local + .env.example | Vite built-in support; clear documentation of required vars | Config management |

### Deployment

| Component | Technology | Rationale | Purpose |
|---|---|---|---|
| **Build Output** | Static SPA (dist/) | No SSR needed; served by CDN or simple HTTP server; cacheable assets | Production build |
| **Hosting (Self-Hosted)** | Nginx reverse proxy + Docker | Minimal footprint; serves static assets + proxies /api to backend | Self-hosted deployment |
| **Hosting (Cloud)** | Vercel or Netlify (optional) | One-command deploy; auto-staging; analytics; functions for edge logic | Cloud deployment |
| **Docker** | Node.js 20-alpine (builder) + nginx:alpine (runtime) | Multi-stage build; minimal final image size; nginx for efficient static serving | Containerized deployment |

---

## Infrastructure & DevOps

### Containerization

| Component | Technology | Rationale | Purpose |
|---|---|---|---|
| **Container Runtime** | Docker | Industry standard; Dockerfile for reproducible builds | Containerization |
| **Orchestration** | Kubernetes (optional for scale) | Docker Compose for dev/single-server; K8s for multi-region scale | Container orchestration |
| **Image Registry** | Docker Hub or private ECR | Public for OSS; private for enterprise images | Image storage |

### CI/CD Pipeline

| Component | Technology | Rationale | Purpose |
|---|---|---|---|
| **CI Platform** | GitHub Actions | Free for public repos; integrated with GitHub; sufficient for MVP | Automation |
| **Stages** | Lint → Test → Build → Deploy | Standard pipeline; catches issues early; reproducible builds | Code quality gates |
| **Artifact Storage** | GitHub Artifacts (CI) / Docker Hub (images) | Temporary CI artifacts; persistent Docker image registry | Build artifacts |

### Monitoring & Observability (Phase 2)

| Component | Technology | Rationale | Purpose |
|---|---|---|---|
| **Logs** | Structured JSON logs (backend) + browser console (frontend) | ELK stack optional; JSON enables machine parsing | Log aggregation |
| **Metrics** | Prometheus-compatible endpoint (backend) | Counterpart Grafana dashboards; industry standard | Metrics collection |
| **Tracing** | OpenTelemetry (optional) | Distributed tracing for multi-service requests | Request tracing |
| **Alerts** | Prometheus AlertManager + PagerDuty (optional) | Route critical alerts to on-call | Alert routing |

---

## Data Storage & Retrieval

### Vector Embeddings Pipeline

| Stage | Technology | Input | Output |
|---|---|---|---|
| **Encode Dense** | BGE-M3 (BAAI) | Text chunks (up to 8,192 tokens) | 384-dim dense vectors |
| **Encode Sparse** | BGE-M3 built-in | Text chunks | Sparse BM25-like vectors |
| **Index Dense** | Qdrant HNSW | 384-dim vectors | HNSW graph (fast ANN search) |
| **Index Sparse** | Qdrant sparse index | Sparse vectors | Inverted index |
| **Fuse Rankings** | RRF (Reciprocal Rank Fusion) | Top 50 dense + Top 50 sparse | Top 50 merged by score |
| **Rerank** | BGE-reranker-v2-m3 | Top 50 fused results + query | Top 5 re-ranked |
| **Compress Context** | LLMContextCompress (custom) | Top 5 chunks (2–3 pages) | Summarised, deduplicated context |

### Similarity Metrics

| Query Type | Metric | Notes |
|---|---|---|
| **Semantic search** (dense) | Cosine similarity | Default; works well for queries with paraphrasing |
| **Keyword search** (sparse) | BM25-equivalent | Catches exact phrase matches |
| **Hybrid** (both) | RRF | Merges dense + sparse scores deterministically |

---

## ML / NLP Components

### Transformer Models (Hosted Locally or via API)

| Model | Purpose | Provider | Size | Cost |
|---|---|---|---|---|
| **BGE-M3** | Dense + Sparse embedding | Hugging Face (self-host) | 568M | Free |
| **BGE-reranker-v2-m3** | Re-ranking | Hugging Face (self-host) | 1.2B | Free |
| **GLiNER (base)** | PII detection | Hugging Face (self-host) | 333M | Free |
| **Claude 3.5 Sonnet** | Generator + Critic LLM | Anthropic API | Hosted | $3/1M tokens input |
| **Claude 3 Haiku** | Lightweight summarization | Anthropic API | Hosted | $0.80/1M tokens input |
| **Mistral-7B** | Air-gapped fallback | Ollama (self-host) | 7B | Free (inference) |

### NLP Pipelines (Python)

| Component | Library | Purpose |
|---|---|---|
| **Tokenization** | spaCy v3 | Sentence tokenization, POS tagging for chunking logic |
| **Text Preprocessing** | NLTK / spaCy | Stop word removal, lemmatization for sparse indexing |
| **Named Entity Recognition** | GLiNER + spaCy | PII detection (GLiNER), domain entities (spaCy) |
| **Semantic Similarity** | BGE-M3 locally | Chunk-to-chunk similarity for deduplication |

---

## Deployment Targets

### Target 1: Self-Hosted (Single Server)

**Stack:**
- PostgreSQL 15 (primary DB)
- Redis (cache + queues)
- Qdrant (vector DB)
- FastAPI backend (single process + Gunicorn)
- React SPA frontend (Nginx)
- Ollama (optional, for air-gapped)

**Deployment:**
```bash
docker-compose up -d  # Prod-grade docker-compose.yml with all services
```

**Hardware:** 8 vCPU, 32GB RAM, 500GB SSD (scales to 4TB for large deployments)

### Target 2: Kubernetes Multi-Region

**Services:**
- PostgreSQL (managed RDS / Cloud SQL) + read replicas
- Redis Cluster (Upstash / ElastiCache)
- Qdrant cluster (Helm chart, S3 backup)
- FastAPI service (HPA auto-scaling)
- React frontend (CDN + load balancer)

**Deployment:** Helm charts (phase 2)

### Target 3: Hybrid Air-Gapped (No External APIs)

**Fallbacks:**
- Ollama (Mistral-7B) instead of Claude API
- Local embeddings (BGE-M3 on CPU or GPU)
- Self-hosted Firecrawl instance (optional)
- No external search (Tavily fallback disabled)

**Data Compliance:** GDPR/HIPAA/FedRAMP ready

---

## Summary: MVP Tech Stack Checklist

- [x] Backend: FastAPI + PostgreSQL + Redis + Qdrant
- [x] LLM: Claude 3.5 Sonnet (primary) + Haiku (secondary)
- [x] Frontend: React 18 + TypeScript + Vite + shadcn/ui
- [x] Ingestion: Docling + GLiNER + semantic chunking
- [x] Retrieval: BGE-M3 + RRF + BGE-reranker-v2-m3
- [x] Validation: Generator + Critic (LangGraph)
- [x] Real-Time: WebSocket + Redis pub/sub
- [x] Auth: JWT + httpOnly cookies
- [x] Deployment: Docker + docker-compose (MVP) + Kubernetes (scale)

---

## Phase 2 Additions

- [ ] Monitoring: Prometheus + Grafana
- [ ] Tracing: OpenTelemetry + Jaeger
- [ ] Advanced Auth: OAuth2 + SSO (OIDC)
- [ ] Knowledge Graph: Neo4j or Qdrant knowledge graph mode
- [ ] Caching Strategy: Edge caching via CDN
- [ ] Rate Limiting: Redis-based token bucket
- [ ] Webhook Signing: HMAC for security
