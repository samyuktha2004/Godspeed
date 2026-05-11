# Godspeed — Product Requirements Document

**Version:** 0.1 MVP  
**Audience:** Engineering teams, internal stakeholders  
**Last updated:** 2026-05-11

---

## 1. Product Overview

Godspeed is an AI-powered knowledge copilot for engineering organisations. It gives every team member — from new hires to senior engineers — instant, accurate answers from the company's fragmented knowledge base: docs, tickets, Slack threads, code, incident reports, and runbooks.

Instead of searching across six tools, you ask one question. Godspeed retrieves, synthesises, and cites its sources, then visualises the knowledge graph so you can explore relationships between services, teams, and incidents.

---

## 2. Target Audience

| Persona | Age range | Primary goal | Technical level |
|---|---|---|---|
| **End user / engineer** | 22 – 45 | Get answers fast without asking colleagues | Medium–high |
| **New hire** | 22 – 30 | Onboard to a large, unfamiliar codebase | Low–medium |
| **Analyst / team lead** | 28 – 50 | Understand knowledge health, dependency risks, escalation patterns | Medium |
| **Admin / DevOps** | 25 – 50 | Manage data sources, monitor system health, manage users | High |
| **Non-technical stakeholder** | 35 – 65 | Search for policies, runbooks, team contacts | Low |

**Design principles from the audience:**
- Professionals expect speed and no fluff. Results appear as they load — no waiting for the full answer.
- 22-year-olds and 65-year-olds share the same interface. Interactions must be obvious without instructions.
- Error messages are written for humans, not logs. Technical details go to system logs only.
- Nothing disappears. Partial results, previous queries, and in-progress graph data all remain visible.

---

## 3. Core Features

### 3.1 Multi-agent Query System

**What it does:** When a user submits a query, a LangGraph-orchestrated agent pipeline fans out across multiple retrieval agents simultaneously, then synthesises results into a single coherent answer.

**Agents:**
- `doc_search` — semantic search over ingested documents (Qdrant vector store + BM25 hybrid)
- `ticket_lookup` — Jira/Linear ticket retrieval
- `live_docs` — Confluence / GitHub wiki lookup
- `summariser` — synthesis agent that fuses agent outputs, cites sources

**User-visible behaviour:**
- Agent status badges appear as soon as the execution plan is ready
- Each badge transitions: pending → active (pulsing) → done (✓ + confidence level)
- Answer streams in token by token; user can read while agents are still running
- If one agent fails, others continue and the answer is still produced with a note

**Backend:** `POST /agent/query` — SSE stream. Events: `plan_ready`, `agent_started`, `agent_done`, `citations`, `answer_chunk`, `guardrail_result`, `done`, `error`.

> **Retry behaviour:** If the answer drops mid-stream, the partial text remains visible with a "connection dropped" warning and a Retry button. Retry re-runs the full pipeline from scratch — partial resumption requires backend changes (phase 2).

---

### 3.2 Real-time Knowledge Graph Visualisation

**What it does:** As the agent runs, a parallel WebSocket stream (`WS /graph/stream`) pushes graph nodes and edges that represent the knowledge entities relevant to the answer. The graph populates in real time — users see it build as the query runs.

**Node types (colour coded):**
- Service — blue (#3b82f6)
- Library — green (#22c55e)
- Incident — red (#ef4444)
- Team — orange (#f97316)

**Edge types:** DEPENDS_ON, CAUSED_BY, OWNED_BY, MENTIONS, REFERENCES, HAS_CHUNK, DOCUMENTS

**Interactions:**
- Hover a node → tooltip with name and label
- Click a node → side panel with related documents and "Ask about this node" shortcut
- Node count and edge count displayed below the graph as it builds
- WS auto-reconnects up to 5 times with exponential backoff if the connection drops. After max retries a "Try again" button is shown — reconnecting re-runs the full Neo4j snapshot so any data updated since last load appears automatically.
- A "↻ Refresh graph" control is available after a successful load, letting users pull in freshly ingested data without re-running their query.

> **Architecture note:** The graph stream is a global Neo4j snapshot (`MATCH (n) WHERE NOT n:Chunk`) — it is not scoped to the current query or to the user's team. Every connection/reconnect fetches fresh live data. Team-scoped graph filtering is a phase 2 item.

**Desktop layout:** Graph always visible in the right column (380px) alongside the answer. Graph canvas mounts the moment a query is submitted and starts populating with the first node/edge — no loading screen.

**Mobile:** Graph and Answer are in separate tabs. Graph tab is the default. Answer tab is grey/disabled until the first SSE event arrives (nothing to show yet). Tab unlocks and becomes clickable once data is available.

---

### 3.3 Answer Streaming & Citations

**What it does:** The answer streams in as the synthesiser agent produces tokens. Citations appear as expandable source cards below the answer.

**Citation fields:** source name, source type (doc/ticket/wiki), relevance score, reranker score, chunk preview.

**Related docs:** When more than 3 citations exist, overflow documents appear in a "Related documents" section below citations.

**Guardrail:** If the synthesiser's confidence is low, a yellow "This answer may not be fully accurate" banner appears with a suggestion to verify sources before acting.

---

### 3.4 Feedback System

**What it does:** After each completed answer, the user can rate the response. Feedback is stored in Redis and can be surfaced to admins for quality monitoring.

**User flow (👍 path):**
1. User clicks 👍 → `POST /api/query/{queryId}/feedback` with `{ sentiment: "helpful" }`
2. Toast: "Feedback recorded — thank you"
3. Button replaced with "👍 Marked as helpful"

**User flow (👎 path):**
1. User clicks 👎 → inline form expands asking "What was wrong?"
2. Optional free-text field for context
3. Two options: "Not helpful" (`sentiment: not_helpful`) or "Flag as hallucination" (`sentiment: hallucinated`)
4. On submit: toast + confirmation text
5. On cancel: form collapses, buttons remain

**Data stored:** `gs:feedback:{queryId}` key in Redis with sentiment + text, TTL 30 days.

---

### 3.5 Query History & Workspace

**What it does:** Every completed query (success or failure) is stored in Redis and available in the workspace. Users can browse, expand, and replay past queries.

**History endpoint:** `GET /api/workspace/history?page=N&limit=20` → paginated list.

**History item fields:** query text, brief answer summary, timestamp, success/failure dot, duration.

**Replay:** "Ask again →" re-submits the exact query text to the agent pipeline.

**Sidebar integration:** The 6 most recent queries appear in the collapsible left sidebar for quick replay without navigating to the History page.

---

### 3.6 Collapsible Sidebar Navigation

**What it does:** A fixed left sidebar on desktop (≥1024px) provides navigation, recent query history, notifications, theme toggle, and account management. Collapses to icon-only mode (56px) to maximise content space.

**Collapsed state:** Icons only, tooltips on hover, avatar initial for user section.
**Expanded state (240px):** Full labels, ⌘K badge on Ask, 6 recent queries, user name + email, sign out.

**Navigation links:** Home, Ask (⌘K), History, Analytics, Admin (admin role only).

**Sidebar state** is persisted to localStorage via zustand. Mobile uses the original top NavBar.

---

### 3.7 Analytics Dashboard

Four tabs accessible to analysts and admins:

| Tab | Data source | What it shows |
|---|---|---|
| **Queries** | Redis `gs:queries` list | Total queries, unique users, avg response time, success rate, daily trend chart |
| **Knowledge Health** | Neo4j node counts | Coverage/freshness/accuracy per domain (Service, Library, Incident, Team), radar chart |
| **Dependencies** | Neo4j nodes | Service/library nodes with version comparison, outdated/breaking change flags |
| **Escalations** | Redis `gs:escalations` | Open/in-progress/resolved escalations table, filter by status |
| **Export** | All of the above | CSV download of query events by date range |

Date range filter: 7d / 30d / 90d / all.

---

### 3.8 Admin Panel

Three tabs visible to admin role only:

| Tab | Feature |
|---|---|
| **System Status** | Live health cards for Neo4j, Redis, Qdrant — each shows OK/error state |
| **Data Sources** | Toggle integrations on/off (Jira, Confluence, GitHub, Slack), seeded from env vars, state persisted in Redis |
| **System Logs** | Live WebSocket log tail (`WS /ws/logs`) — filter by level, search, pause/resume, 500-line ring buffer |
| **Ingest** | Trigger graph ingest or file upload for ingestion pipeline |

---

### 3.9 Authentication

Session-cookie-based auth backed by Redis. Two configurable personas via env vars (`DEMO_EMAIL`, `ADMIN_EMAIL`).

- Login: `POST /api/auth/login` → sets `gs_session` cookie (HttpOnly, SameSite=Lax, 8h TTL)
- Session validated on app mount via `POST /api/auth/refresh` — stale localStorage is cleared if server rejects
- Logout: `POST /api/auth/logout` → deletes session from Redis, clears cookie
- `cookie_secure = true` must be set in prod to enable Secure flag on the cookie

---

### 3.10 Error Handling — User-Facing Language

All error messages visible to users are written in plain language. Technical details (stack traces, error codes, Redis keys) go to the structured JSON log (`/ws/logs`) only.

| Scenario | User sees |
|---|---|
| Query timeout (>30s) | "The query took too long to respond. This can happen when agents are under heavy load. Try again in a moment." + Retry button |
| Answer cut off mid-stream | "Answer may be incomplete — connection dropped mid-stream." + Retry button |
| Graph stream lost | "Having trouble loading the knowledge graph — trying again (X of 5)…" |
| Low-confidence answer | "This answer may not be fully accurate. Verify against the cited sources before acting on it." |
| Login failed | "Invalid credentials" (no detail that reveals which field is wrong) |
| Redis unavailable on login | "Session store unavailable — try again shortly" (503) |
| Feedback failed | "Could not submit feedback" toast |
| No results | "No results found for [query]" with suggested reformulations |

---

## 4. Navigation & Layout

### Desktop (≥ 1024px)
```
┌──────────────────────────────────────────────────────────┐
│ [Sidebar 240px / 56px]  │  Main content (flex-1)        │
│                          │                               │
│  Godspeed (logo)  [<]    │  SearchBox                    │
│                          │                               │
│  Home                    │  ┌─────────────┬──────────┐   │
│  Ask          ⌘K         │  │ Answer col  │ Graph col│   │
│  History                 │  │             │  (380px) │   │
│  Analytics               │  │ Agent badges│          │   │
│  Admin (admin only)      │  │ Answer text │  Force   │   │
│  Notifications           │  │ Citations   │  Graph   │   │
│                          │  │             │          │   │
│  ── Recent ──            │  └─────────────┴──────────┘   │
│  > last query 1          │                               │
│  > last query 2          │                               │
│                          │                               │
│  [Moon] Dark mode        │                               │
│  [avatar] Jane  [→]      │                               │
└──────────────────────────────────────────────────────────┘
```

### Mobile (< 1024px)
```
┌──────────────────────────┐
│ Godspeed     🔔  👤  [☀]  │  ← NavBar
├──────────────────────────┤
│ SearchBox                │
│                          │
│ [  Graph  |  Answer  ]   │  ← Tab bar (Answer disabled until SSE data)
│                          │
│ [  Force graph canvas ]  │  ← Graph tab (default)
└──────────────────────────┘
```

---

## 5. Known Gaps & Planned Improvements

### End User
- [ ] No "save answer" / bookmark feature — users can't pin answers for later reference
- [ ] No copy-as-markdown button on the answer card
- [ ] Follow-up questions don't carry conversation context — each is a fresh query
- [ ] Knowledge graph has no "fit to screen" / zoom reset button
- [ ] No keyboard navigation within the force graph
- [ ] Suggested topics on Home page are static — don't adapt to user history or role
- [ ] No "explain like I'm new" mode for adjusting answer depth

### New Hire
- [ ] No guided onboarding flow / interactive tour
- [ ] No progress tracking (topics explored, questions asked this week)
- [ ] Suggested queries don't differentiate between new users and experienced ones
- [ ] No "getting started" checklist or recommended first queries

### Analyst
- [ ] Knowledge health `freshness` and `accuracy` values are hardcoded (0.85, 0.90) — not derived from real data
- [ ] No time-period comparison in analytics (e.g., this week vs. last week)
- [ ] No per-agent performance breakdown (which agent has the most low-confidence results?)
- [ ] Export only covers query events — no export of graph data or health scores

### Admin
- [ ] No user management UI (add users, change roles, deactivate accounts) — credentials are env-var only
- [ ] No audit log UI (who queried what, when)
- [ ] Data source sync status is static — no live progress when a sync is running
- [ ] No webhook configuration UI
- [ ] No rate limiting on the query endpoint
- [ ] `freshness` and `accuracy` in knowledge health need real calculation logic (last ingestion timestamp, validation pipeline)

### Cross-cutting
- [ ] Share Results feature sends only the query text — not the graph state or answer
- [ ] No persistent "projects" or "collections" to group related queries
- [ ] Notifications (WS `/ws` endpoint) exist but no backend events push to them yet
- [ ] PDF export in Analytics is a stub (returns plain text fallback)
- [ ] No dark-mode persistence of the force-graph canvas background — always transparent

---

## 8. Phase 2 — Team Projects & Shared Wikis

**Current state (MVP):** Query history (`gs:queries`) is a single global Redis list. All logged-in users see all queries. The graph snapshot is global — not filtered by team. `team_id` is passed to agent queries for retrieval context but is not used for access control or grouping anywhere in the system.

**Phase 2 scope:**

| Feature | What it needs |
|---|---|
| Team projects | Project CRUD (name, description, team_id), associate queries with a project, project-scoped history view |
| Shared wikis | Per-project document collections, invite team members to a project, read-only sharing links |
| Team-scoped history | `/api/workspace/history?team_id={id}` filter; Redis history key per team (`gs:queries:{team_id}`) |
| Team-scoped graph | `/graph/stream?team_id={id}` — filter Neo4j nodes by `team` property |
| Access control | Role × team matrix (who can read/write which projects); currently roles are global not team-scoped |
| Per-team ingestion | Confluence space key per team, GitHub org filter per team, stored in data sources config |

**What already exists that supports phase 2:**
- `user.team_id` and `user.team` on the User object
- `team_id` passed to every agent query — the agent uses it for retrieval filtering already
- `team` property on Neo4j Service/Library nodes (set by ingestion pipeline)
- `team_id` stored on each query event in Redis

---

## 6. Tech Stack Summary

| Layer | Technology |
|---|---|
| Frontend | React 18, TanStack Router, TanStack Query, Zustand, Tailwind CSS, Radix UI |
| Agent orchestration | LangGraph 0.2.x, Gemini 2.5 Pro/Flash via langchain-google-genai |
| Vector search | Qdrant (local: host+port; hosted: QDRANT_URL + QDRANT_API_KEY) |
| Graph store | Neo4j 5.x async driver |
| Session / analytics store | Redis (aioredis) |
| Embeddings | BAAI/bge-large-en via FlagEmbedding |
| Reranker | BAAI/bge-reranker via FlagEmbedding |
| PII masking | GLiNER (local, zero egress) |
| API server | FastAPI 0.115, uvicorn |
| Document parsing | docling 2.x, PyMuPDF, pdfplumber, python-docx |

---

## 7. Environment Variables Reference

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `VITE_API_BASE_URL` | ✓ | — | Frontend → backend HTTP base URL |
| `VITE_WS_BASE_URL` | ✓ | — | Frontend → backend WebSocket base URL |
| `REDIS_URL` | ✓ | `redis://localhost:6379/0` | Redis connection string |
| `DEMO_EMAIL` | — | `demo@godspeed.local` | Demo user email |
| `DEMO_PASSWORD` | — | `demo` | Demo user password |
| `ADMIN_EMAIL` | — | `admin@godspeed.local` | Admin user email |
| `ADMIN_PASSWORD` | — | `admin` | Admin user password |
| `CORS_ORIGINS` | ✓ prod | `http://localhost:5173,...` | Comma-separated allowed origins |
| `COOKIE_SECURE` | ✓ prod | `false` | Set `true` behind HTTPS |
| `QDRANT_URL` | hosted | `""` | Qdrant Cloud cluster URL |
| `QDRANT_API_KEY` | hosted | `""` | Qdrant Cloud API key |
