# Frontend Build — TODO

> Ordered by dependency. Each group can be started once the group above it is done.
> Backend is complete. Frontend only consumes `POST /agent/query` (SSE) and `WS /graph/stream` (WebSocket) plus standard REST endpoints.

---

## ✅ Security + Performance + Cleanup Pass (done)

End-to-end sweep produced two passes of fixes; see `C:\Users\sanan\.claude\plans\do-an-end-to-end-sweep-majestic-harbor.md` and `reduce-weight-and-latency.md` for the full punch-lists.

**Security (critical/high):**
- `/ingest/confluence`, `/github`, `/upload`, `/jobs/{id}` — all now require `Depends(get_current_user)`; team_id is enforced against the session unless caller is `admin`/`org_admin`.
- `/api/ingest/file` and `/api/ingest/folder` (`src/file_agent/router.py`) — same auth dep added. Folder ingest is admin-only and rejects paths outside `FILE_WATCH_FOLDER` (path-traversal guard).
- `/api/workspace/history` and `/api/query/{id}/feedback` — now authed; history is team-scoped.
- New `OriginCheckMiddleware` in `src/utils/middleware.py` — rejects state-changing requests whose `Origin`/`Referer` is not in `CORS_ORIGINS` (defense-in-depth for `SameSite=None` deploys, e.g. HF Spaces). CORS `allow_methods` narrowed from `["*"]` to an explicit list.
- Hardcoded demo/admin credentials gated behind new `ALLOW_DEMO_AUTH` env var (default `false`).
- In-memory session fallback now enforces `SESSION_TTL` (stored as `(payload, expires_at)`).
- `QueryInput.query` has `max_length=10_000`; file uploads cap at 50 MB (file agent) and 25 MB (ingestion PDF).
- `/health` now returns HTTP 503 when any subsystem is degraded (was always 200).

**Performance / weight:**
- `.env.example` model defaults flipped Pro → Flash for planner + synthesiser (50–60 s queries down to 3–10 s; matches the in-code default in `agent/config.py`).
- Removed unused frontend deps `framer-motion` and `@tanstack/react-table` (~250 KB off the bundle).
- `Dockerfile` BGE-M3 pre-download now uses `use_fp16=True` to match runtime — saves ~1 GB in the image.
- Singleton Redis + Qdrant clients (`src/utils/clients.py`) wired through every per-request call site. ~50–200 ms saved per cookie-bearing request; no more `TIME_WAIT` churn.
- `agent/api.py` analytics writes pipelined (~6 RTTs → 1) and moved to a background `asyncio.create_task` so SSE close is immediate.
- `agent/tools/slack_search.py` — one `httpx.AsyncClient` shared across the channels loop (was creating 10 per query).

**Wiring/quality:**
- `RetrievedChunk` model gained the `metadata` field that `ticket_lookup`/`confluence_search` already passed.
- `graph_store/stream.py` reuses the shared Neo4j driver (`get_driver()`); per-request driver creation removed.
- `Celery` worker config got `worker_concurrency=4`, `worker_prefetch_multiplier=1`, `task_acks_late=True`.
- `ingestion/storage/qdrant_store.py:delete_chunks_for_doc` tolerates "collection doesn't exist" on first ingest (was aborting whole job).
- `src/analytics/router.py:/knowledge-health` + `/dependencies` reuse `graph_store/writer.get_driver()` instead of opening a per-request driver.
- API Keys tab hidden behind `VITE_ENABLE_API_KEYS` until backend `/api/settings/api-keys` endpoints ship (S13 below).

**Disproven / left as-is:**
- `agent/api.py:172-176` admin RBAC bypass is **correct** — admins get `allowed_channel_ids=[]` which routes `doc_search` to the team_id-only filter, matching the commit intent.
- `agent/tools/summariser.py` is intentionally a stub for future map-reduce summarisation; the planner enum + fallback edge in `agent/graph.py:321` is the design hook. Do not remove.
- `agent/tools/live_docs.py` same pattern.

---

## ✅ Persona Gap-Fix Pass (done)

End-to-end runthrough across 4 personas (end-user, admin, analyst, new user) found and fixed:

**Backend gaps fixed:**
- `src/config.py` — added `redis_url`, `qdrant_host`, `qdrant_port`, `auth_secret`, `demo_email/password`, `admin_email/password`, `cors_origins` fields
- `main.py` — added `CORSMiddleware` (origins from `CORS_ORIGINS` env); mounted 5 new routers; fixed `redis_url` reference in health endpoint
- `src/auth/router.py` — NEW: `POST /api/auth/login`, `/logout`, `/refresh` — session-cookie auth backed by Redis, two hardcoded dev personas (demo/admin) configurable via env
- `src/analytics/router.py` — NEW: `GET /api/analytics/queries`, `/topics`, `/knowledge-health`, `/dependencies`, `/escalations`, `/export` — aggregates from Redis query event list + Neo4j graph data
- `src/admin/router.py` — NEW: `GET /api/admin/data-sources`, `PATCH /api/admin/data-sources/{id}` — enabled toggle, seeded from env vars on first call, persisted in Redis
- `src/workspace/router.py` — NEW: `GET /api/workspace/history`, `POST /api/query/{id}/feedback` — reads/writes `gs:queries` Redis list
- `src/ws/router.py` — NEW: `WS /ws` (notification broadcast), `WS /ws/logs` (log tail with 200-line ring buffer + `_WSLogHandler` on root logger)
- `agent/api.py` — now stores each completed query to Redis (`gs:queries` list, `gs:topics` sorted set) for analytics and history

**Frontend gaps fixed:**
- `NavBar.tsx` — user avatar, name, and "Sign out" button (calls `signOut()` + redirects to `/login`)
- `authStore.ts` — `onRehydrateStorage` re-derives `isAuthenticated = user !== null` after localStorage hydration, preventing stale flag
- `App.tsx` — on mount with a persisted user, fires `POST /api/auth/refresh`; if server rejects (expired/invalid), clears store and redirects to `/login`; network failure is a no-op (lazy handling)
- `.env.example` (root) — added `AUTH_SECRET`, `DEMO_EMAIL/PASSWORD`, `ADMIN_EMAIL/PASSWORD`, `CORS_ORIGINS`
- `frontend/.env.example` — added descriptions for both required vars

**Remaining known gaps (non-blocking):**
- [x] ~~`WS /ws` notifications: no event sources trigger it yet~~ — **corrected, this is done.** `src/anomaly/notifier.py:broadcast_new_critical_signals()` pushes critical/high `anomaly_signals` rows via `broadcast_notification()`, triggered as a `BackgroundTask` from `GET /api/anomaly/signals` (rate-limited to once per 5 min). The Proactive Intelligence Agent gap from `03_analytics_and_intelligence.md` is effectively closed.
- [ ] Remaining gap in the above: the push only fires when *someone* hits `GET /api/anomaly/signals` (e.g. a manager viewing `ManagerTeamView.tsx`, which does a one-time fetch on mount, not polling) — there's no independent scheduler, so if nobody views that page, no push happens even for a critical signal. Closing this needs either a Celery Beat task calling `broadcast_new_critical_signals()` directly (works even without a Celery process import quirk — check `src/anomaly/notifier.py`'s docstring on why it currently must run in the API process) or a short client-side poll interval on the anomaly signals query.
- [ ] Analytics `/knowledge-health`, `/dependencies` require Neo4j nodes to have `version`, `latest_version`, `breaking_change` properties — populated by graph extraction pipeline
- [ ] PDF export in `AnalyticsExport.tsx` returns a plain text fallback; a real PDF renderer (e.g. `weasyprint`) can be added post-MVP

---

## ✅ Backend — Logging (done)

- `src/utils/logger.py` — JSON structured logger, `request_id_var` ContextVar, `Timer` context manager
- `src/utils/middleware.py` — `RequestLoggingMiddleware` (UUID per request, `X-Request-ID` header, request_start/request_end logs)
- `main.py` — middleware registered, `GET /health` endpoint (Neo4j/Redis/Qdrant ping with 3s timeout)
- `agent/api.py`, `graph_store/api.py`, `src/jira_agent/router.py`, `src/confluence_agent/router.py`, `src/file_agent/router.py` — all switched to structured logging with Timer and relevant fields

Remaining:
- [ ] Add Celery task logging in `src/jira_agent/tasks.py`, `src/confluence_agent/tasks.py`, `src/file_agent/tasks.py`
- [ ] Add `GET /api/admin/webhook-events` endpoint (reads last 50 events from Redis)

---

## ✅ Frontend — Error Handling & Design System (done)

- `lib/http.ts` — `ApiError` class, 429/403/502-504/500/network error handling, `X-Request-ID` surfaced in toasts
- `useSSEStream.ts` — malformed line counter (>5 → synthetic error), mid-stream drop detection (amber banner, partial answer kept)
- `FileUploadWidget.tsx`, `SyncTrigger.tsx`, `GraphIngestButton.tsx`, `HealthCards.tsx` — all built with full error states

---

---

## ✅ Done — Scaffold, Config, Types, State, Auth, Core Hooks

All of the following are built and in `frontend/src/`:

- Config: `env.ts`, `queryClient.ts`, `routes.ts` (with inline `beforeLoad: requireAuth` auth guard)
- Types: `types/api.ts`, `types/user.ts`, `types/errors.ts`
- Stores: `stores/authStore.ts`, `stores/uiStore.ts`, `stores/filterStore.ts`
- Auth: `pages/LoginPage.tsx`, `hooks/useAuth.ts`, `lib/http.ts` (JWT refresh interceptor)
- Shared UI: `components/common/LoadingSkeleton.tsx`, `components/common/ErrorBoundary.tsx`, `components/common/Toast.tsx`
- Hooks: `hooks/useSSEStream.ts`, `hooks/useGraphStream.ts`, `hooks/useAuth.ts`, `hooks/useDebounce.ts`
- Entry: `main.tsx`, `App.tsx`, `styles/globals.css`

---

## ✅ Group 3 — Remaining Shared UI (done)

Built: `HallucinationWarning`, `RBACRestrictedBanner`, `NoResultsState`, `TimeoutError`, `NetworkRetry`

Also done: Group 4 core query interface — `SearchBox`, `SuggestedTopics`, `AgentBadges`, `Answer`, `Citations`, `RelatedDocs`, `FollowUp`, `ResultsPage`, updated `Home.tsx` + `QueryPage.tsx`

---

## ✅ Group 4 — Core Query Interface (done)

Built: `SearchBox`, `SuggestedTopics`, `AgentBadges`, `Answer` (react-markdown + rehype-highlight, bash copy button), `Citations`, `RelatedDocs`, `FollowUp`, `ResultsPage` (full SSE state machine, two-column layout, graph wired). `Home.tsx` and `QueryPage.tsx` updated from stubs.

---

## ✅ Group 5 — Knowledge Graph (done)

Built: `KnowledgeGraph.tsx` (Force-Graph 2D canvas, imperative ref pattern, dynamic import for code splitting), `GraphNodeTooltip.tsx` (fixed-position viewport-clamped hover overlay), `GraphNodeDetailPanel.tsx` (Radix Dialog, `/graph/traverse` fetch via TanStack Query, "Ask about this" CTA).

`ResultsPage.tsx` updated: two-column layout on lg (answer | graph), `useGraphStream` wired to reset + reconnect on each new query, `NetworkRetry` shown during WS backoff, tooltip and detail panel wired up. `GraphDoneEvent` type fixed to match backend (`nodes`/`edges` not `nodes_count`/`edges_count`).

### 5a — Canvas Component

- [ ] Build `KnowledgeGraph.tsx` — Force-Graph 2D canvas panel
  - Mount via `useEffect(() => { graphInstance = ForceGraph2D(containerRef.current) ... })` — imperative, not JSX
  - Node colour map: `Service`=`#3b82f6` (blue), `Library`=`#22c55e` (green), `Incident`=`#ef4444` (red), `Team`=`#f97316` (orange)
  - Node label: node `name` field, shown in canvas below each node
  - Link colour: `#94a3b8` (slate-400); edge label: `rel` type shown on hover only
  - Feed data incrementally: on each `onNode`/`onEdge` callback, call `graphInstance.graphData({nodes:[...], links:[...]})` with the full accumulated array (not just the new item — force-graph replaces, not appends)
  - Keep local `nodesMap: Map<string, ForceNode>` and `linksArr: ForceLink[]` in refs to avoid React re-renders on every message
  - Canvas fills the container div; container is `w-full h-[400px]` (fixed height) on desktop, hidden (`hidden lg:block`) on mobile
  - Cleanup: return a teardown function from `useEffect` that calls `graphInstance._destructor()` (force-graph cleanup method)
  - Props: `onNodeClick(node: GraphNode): void`, `onNodeHover(node: GraphNode | null): void`, `firstNodeArrived: React.RefObject<boolean>`

### 5b — Tooltip

- [ ] Build `GraphNodeTooltip.tsx` — overlay shown while a node is hovered
  - Controlled by parent via `hoveredNode: GraphNode | null` and canvas-relative `{x, y}` coordinates from `onNodeHover`'s `(node, prevNode, event)` callback
  - Renders a small card: node name (bold) + type badge coloured to match node colour
  - Position: `position:fixed`, offset 12px from cursor; clamp to viewport edges so it never overflows
  - Disappears immediately when `hoveredNode` is null

### 5c — Detail Panel

- [ ] Build `GraphNodeDetailPanel.tsx` — Radix `Dialog` (or sheet) opened on node click
  - Header: entity name + type badge
  - Body: calls `GET /graph/traverse?type=<label.toLowerCase()>&name=<name>&team_id=<team_id>` via TanStack Query on open
  - Shows up to 6 related text chunks as card list; each chunk shows first 200 chars of text
  - Loading state: `LoadingSkeleton` inside the panel while traverse is fetching
  - Empty state: "No related documents found" if chunks array is empty
  - Footer button: "Ask about this" — closes panel and calls parent `onAskAbout(node.name)` so `SearchBox` is pre-filled
  - Error state: if traverse returns error, show inline "Could not load related documents" with request ID if available

### 5d — Wire into ResultsPage

- [ ] Update `ResultsPage.tsx`:
  - Add `useGraphStream` call; pass `onNode`, `onEdge`, `onDone`, `onError` callbacks that feed `KnowledgeGraph` via a shared state array
  - Connect WS when query starts (call `graphStream.connect(...)` in `runQuery`); disconnect on unmount
  - Show `NetworkRetry` component below graph panel when `gState === 'retrying'`
  - Graph panel skeleton: show `LoadingSkeleton` inside the graph panel container if `state === 'streaming' && !firstNodeArrived.current` (answer is coming but no graph data yet)
  - `onAskAbout` handler: set SearchBox value and submit — re-uses same `runQuery` function with entity name as query
  - On new query: reset node/edge arrays so the graph clears and refills for the new context

---

## ✅ Group 6 — Real-Time Notifications (done)

Built: `useNotifications.ts` (WS `/ws`, graceful no-op on 404, keeps last 50 events, marks read), `NotificationBell.tsx` (unread badge), `NotificationCenter.tsx` (Radix Dialog dropdown panel, mark-all-read, per-type icons).

---

## ✅ Group 7 — Feedback & Share (done)

Built: `QueryFeedback.tsx` (👍/👎, thumbs-down reveals "Flag as hallucination" inline form, `POST /api/query/{id}/feedback`), `ShareResults.tsx` (Radix Dialog, copy-to-clipboard share URL). Both wired into `ResultsPage` complete state.

---

## ✅ Group 8 — Analytics Dashboards (done)

Built: `AnalyticsDashboard.tsx` (tab bar: Overview/Health/Dependencies/Escalations/Export), `QueryTrendChart.tsx`, `TopicsBarChart.tsx`, `SuccessRateGauge.tsx`, `KnowledgeHealthDashboard.tsx` (radar chart + heatmap table), `DependencyTracker.tsx` (filter/sort, version badges, breaking-change flags), `EscalationTable.tsx` (status filter, gap type labels), `AnalyticsExport.tsx` (scope selector, CSV/PDF format, date range). `AnalyticsPage.tsx` updated from stub.

---

## ✅ Group 9 — Admin UI (done)

Built: `AdminDashboard.tsx` (tab bar: System Status / Data Sources / Ingest / System Logs), `DataSourceManager.tsx` (enabled toggle, TanStack Query, add-source placeholder), `SystemLogs.tsx` (live WS log viewer, pause/resume, level+text filter, 500-line ring buffer). Pre-built components (`HealthCards`, `SyncTrigger`, `GraphIngestButton` — now supports teamId-only mode, `FileUploadWidget`) wired into tabs. `AdminPage.tsx` updated from stub.

---

## ✅ Group 10 — Workspace & History (done)

Built: `QueryHistory.tsx` (expandable rows, success indicator, replay handler, paginated). `WorkspacePage.tsx` updated — navigates to `/query?q=...` on replay.

---

## ✅ Group 11 — Cross-Cutting (done)

- Dark mode: already persisted via Zustand `persist` + `partialize`; `App.tsx` applies class on mount and toggle.
- `Cmd+K` / `Ctrl+K` → navigate to `/query` — wired in `App.tsx` via `keydown` handler.
- `NavBar.tsx` built — sticky, links to all pages, active-state highlight, theme toggle button, `⌘K` hint badge.
- `usePagination.ts` hook built — `goTo`, `nextPage`, `prevPage`, `reset`, `canPrev`, `canNext`, `offset`.

---

## Group 12 — Testing

- [ ] Unit tests: `useSSEStream` — mock `fetch` ReadableStream, verify event callbacks fire in order
- [ ] Unit tests: `useGraphStream` — mock WebSocket, verify nodes fed to graph incrementally
- [ ] Unit tests: `LoadingSkeleton` — renders only when `firstEventArrived === false`; gone after first event
- [ ] Unit tests: `Answer.tsx` — bash blocks render with copy button; markdown renders correctly
- [ ] Component tests: `ResultsPage` state machine (idle → loading → streaming → complete → error)
- [ ] E2E (Playwright): full query flow — type query, see streaming answer, graph nodes appear, no skeleton after first token

---

## ⏳ Group 13 — Settings & Admin Workspace (UI done, backend TBD)

### Frontend Built:
- **SettingsDashboard** (`components/settings/SettingsDashboard.tsx`) — main page with tabs
  - `SettingsProfile.tsx` — name, email, password change
  - `SettingsPreferences.tsx` — dark mode, notifications, query settings
  - `SettingsApiKeys.tsx` — add/list/revoke API keys (form + list with masked secrets)
- **AdminWorkspace** (`components/admin/AdminWorkspace.tsx`) — admin panel (role-gated for admin/manager)
  - `AdminUserManagement.tsx` — add single user + bulk CSV/Excel import
  - `AdminChannelManagement.tsx` — create channels with sensitivity levels (public/internal/confidential/restricted)
  - `AdminAuditLog.tsx` — query + admin audit log with filters + CSV export
  - `AdminWorkspaceSettings.tsx` — workspace name, slug, limits
- Route: `settingsRoute` added to `config/routes.ts`; `/settings` link added to NavBar
- Types: `types/settings.ts` with ApiKey, AuditLogEntry, UserInvite, Channel interfaces

### Backend Endpoints Needed:

**Auth/Profile:**
- [ ] `PATCH /api/auth/profile` — update name (email is immutable)
- [ ] `POST /api/auth/change-password` — requires current_password, new_password

**API Keys:**
- [ ] `GET /api/settings/api-keys` — list user's keys (masked, last_used_at, created_at)
- [ ] `POST /api/settings/api-keys` — create new key (provider, name, encrypted_key)
- [ ] `DELETE /api/settings/api-keys/{id}` — revoke key + log to audit_log

**Workspace Users:**
- [ ] `GET /api/workspace/users` — list all users (role-filtered: admins see all, others see their team)
- [ ] `POST /api/workspace/users` — invite single user (email, name, role, team_id, channel_ids)
- [ ] `POST /api/workspace/users/bulk-import` — CSV/Excel upload (parse, validate, send invites)
- [ ] `PATCH /api/workspace/users/{user_id}` — change role, reassign team, toggle active status
- [ ] `DELETE /api/workspace/users/{user_id}` — soft-delete (deactivate) user

**Workspace Channels:**
- [ ] `GET /api/workspace/channels` — list all channels (RLS: only visible channels to user)
- [ ] `POST /api/workspace/channels` — create channel (name, sensitivity, source_type, team_id)
- [ ] `PATCH /api/workspace/channels/{channel_id}` — edit name, sensitivity, role grants
- [ ] `DELETE /api/workspace/channels/{channel_id}` — soft-delete (mark inactive)

**Audit Log:**
- [ ] `GET /api/audit-log?action=X&target_type=Y&limit=50` — fetch audit entries (role-filtered)
- [ ] `GET /api/audit-log/export?format=csv` — export CSV (admin only)

**Database Tables Needed:**
- [ ] `api_keys (id, user_id, workspace_id, provider, name, encrypted_key, created_at, last_used_at, is_active)`
- [ ] RLS policy on `api_keys`: users see only their own

**Encryption:**
- [ ] Store API keys encrypted in DB using `cryptography.fernet` or similar (key from env var)
- [ ] Never log decrypted secrets; log only provider + name + action

**Audit Trail:**
- [ ] All mutations log to `rbac_audit_log` (action: `invite_user`, `bulk_user_import`, `change_role`, `grant_channel`, `revoke_channel`, etc.)

---

## Backend — Not Yet Built (Future Candidates)

> Sourced from a docs sweep that checked every "not built"/"design only" claim in `Docs/` against the actual code. Items below are ones judged worth keeping on the roadmap; everything else that was speculative or had no real path to being needed was removed from the docs rather than tracked here.

### Notion ingestion pipeline (medium effort)

Notion currently only has live on-demand lookup (`tools/tools/notion_tools.py` via `POST /tools/chat`) — no ingestion into Qdrant, unlike Confluence/Jira/File. To bring it to parity:
- [ ] `src/notion_agent/adapter.py` — page tree traversal via Notion API (can reuse `notion_search`/`notion_read_page` from `tools/tools/notion_tools.py` as the fetch layer)
- [ ] `src/notion_agent/chunker.py` — block-to-markdown conversion, following the Confluence chunker's breadcrumb pattern
- [ ] `src/notion_agent/pipeline.py` — chunk → GLiNER PII mask → BGE-M3 embed → Qdrant upsert
- [ ] `src/notion_agent/router.py` — `POST /webhooks/notion` (Notion doesn't have native webhooks; likely needs polling instead — check current API support) + `POST /notion/sync/{workspace_id}`

### GitHub ingestion pipeline (medium effort)

Same gap as Notion, worse given GitHub is called out as a "Core" source throughout the original design docs and no ingestion agent, PyGithub dependency, or `/webhooks/github` endpoint exist — only live lookup (`tools/tools/github_tools.py` via `POST /tools/chat`). This is also the prerequisite for a real Dependency Tracker (needs CHANGELOG/release ingestion).
- [ ] `src/github_agent/adapter.py` — README, `/docs`, CHANGELOG, merged PRs (body only), closed issues with relevant labels — reuse `tools/tools/github_tools.py`'s REST calls as the fetch layer
- [ ] `src/github_agent/chunker.py`, `pipeline.py`, `router.py` — same pattern as `src/confluence_agent/`
- [ ] `POST /webhooks/github` — verify `X-Hub-Signature-256`, handle `push`/`pull_request`/`release` events

### Dependency Tracker (large effort)

Referenced throughout the original design docs (`01`–`05`) as a core differentiator; never built. No `dependency_tracker` module exists.
- [ ] Snapshot + diff: fetch CHANGELOG/release data for libraries the org depends on (GitHub agent already ingests CHANGELOGs — reuse that ingestion)
- [ ] Classify changes (deprecated/removed/signature-changed) — start with an LLM-based changelog parser (Gemini Flash) rather than AST diffing; tree-sitter-based impact scanning is a stretch goal, not a v1 requirement
- [ ] Surface breaking changes in the existing Dependencies analytics tab (`DependencyTracker.tsx` already renders version/breaking-change data from Neo4j nodes — this would populate it with real data instead of manually-tagged nodes)
- Do **not** build the "auto-patch PR" feature from the original design — out of scope; a report is enough.

### Raw text input endpoint (low effort)

`POST /api/ingest/text` — accepts pasted text/markdown, same RBAC/pipeline as file upload. Trivial extension of the already-built `src/file_agent/` pattern; no adapter needed, just a new route + form handling.
- [ ] Add route to `src/file_agent/router.py`: `POST /api/ingest/text` (title, content, access_level, source_reference) → normalize → existing file_agent pipeline

### Complete `agent/tools/live_docs.py` (medium effort — currently a hard stub)

`run_live_docs` unconditionally returns `[]` — it never calls Firecrawl or Tavily even when `FIRECRAWL_API_KEY`/`TAVILY_API_KEY` are set (see the `logger.warning("live_docs: stub returning empty results")` on the line after the key check). This is the T3 "Live Doc Agent" from the original design (see the original doc's fetch/chunk/embed approach, preserved here since the source doc was removed):
- [ ] If `url` is detected in the query (or passed explicitly): call Firecrawl (`scrape_url`, `formats: ["markdown"], onlyMainContent: true`)
- [ ] Else: call Tavily search (`search_depth="advanced", max_results=5, include_raw_content=True`) as the fallback
- [ ] Chunk the fetched content with the existing semantic chunker, embed with BGE-M3, and return as `list[RetrievedChunk]` directly — no ephemeral store needed, since the tool is already called fresh per query and its output flows straight into the same join/synthesis step as `doc_search`
- [ ] Wire `agent/graph.py`'s existing conditional trigger (low `doc_search` confidence OR query names an external library — already described in `agent/README.md`) to actually call the real implementation instead of the stub
- Do not add: ephemeral session-scoped vector store, proactive pre-fetching on dependency-version-detection — those depend on features not built (Dependency Tracker); a stateless per-query fetch is enough for v1.

### NL Analytics Interface for managers (medium effort)

Managers currently get pre-built dashboard tabs (Queries/Health/Dependencies/Escalations — see `PRD.md`), not a free-text question box. `agent/tools/sql_query.py` already does NL→SQL→validated-SELECT→asyncpg execution for query-time retrieval, scoped to `documents`/`chunks`/`ingest_jobs`. The same pattern (LLM SQL generation + forbidden-keyword regex + table allowlist + parameterized execution) is directly reusable for a manager-facing analytics variant:
- [ ] New `src/analytics/nl_query.py` (or similar) — same validation pattern as `agent/tools/sql_query.py`, but with its own `_ALLOWED_TABLES` scoped to `query_events`, `query_events_hourly`, `anomaly_signals` (see [`anomaly-and-forecasting/01_data_layer.md`](./anomaly-and-forecasting/01_data_layer.md)) — keep it a separate allowlist from the content tables, don't widen `sql_query.py` itself
- [ ] New endpoint `POST /api/analytics/nl-query`, gated to manager/admin roles (reuse `require_role` pattern from `src/admin/`)
- [ ] Frontend: a query box on `AnalyticsDashboard.tsx` (new tab or inline on Queries tab)
- Not needed as part of this: the original design's "shown to head/admin for auditability" generated-SQL display is a nice-to-have, add only if requested.

### Cross-Team Silo Detector — reconsidered, still not recommended

Requires per-team topic-embedding clustering + pairwise cosine similarity across all team pairs — no existing infra basis (the anomaly-detection stack is intentionally stdlib-only, no clustering deps) and no demand signal yet. Left off the roadmap; revisit only if a customer/user explicitly asks for cross-team overlap detection.

### Retrieval scaling (backend, deferred from `metadata-scaling-up` work)

Consolidated from `Docs/metadata-scaling-up/04_config_and_operations.md`'s "Deferred" list — these are real, scoped engineering decisions, not speculative:
- [ ] Real BM25-at-scale via an OpenSearch/Elasticsearch lexical tier (current `rank_bm25` is in-memory/O(N), opt-in and off by default)
- [ ] If a flag-on BM25 A/B shows real lexical wins: harden `rank_bm25` into a tenant-safe incremental index, indexed by `team_id`/`channel_id`
- [ ] Physical per-team Qdrant collections/sharding — premature today (payload filtering + indexes suffice), revisit only if query latency data says otherwise
- [ ] Neo4j graph-guided retrieval as a future Stage-0 routing signal (alongside the existing deterministic router)
- [ ] Lock `sql_query` to channel scope (currently team-scoped only)

---

## Scale & Future-Proofing Plan

> These are not MVP blockers. Address them once Groups 6–10 are functional. Ordered by impact-to-effort ratio.

### S1 — API Type Safety (high ROI, low effort)

The backend exposes a full OpenAPI schema at `GET /openapi.json`. Manually maintaining `types/api.ts` will drift over time.

- [ ] Add `openapi-typescript` to devDependencies: generates `types/schema.ts` from the live OpenAPI spec
- [ ] Add `pnpm run gen:types` script: `openapi-typescript http://localhost:8000/openapi.json -o src/types/schema.ts`
- [ ] Migrate `apiFetch` responses to use generated types instead of hand-written interfaces
- [ ] Run codegen in CI before type-check step so drift is caught on every PR

### S2 — Virtual Scrolling for Long Lists (medium ROI, low effort)

Query history, citation lists, and admin tables will grow. Without virtualization they degrade badly at 500+ items.

- [ ] Add `@tanstack/react-virtual` to dependencies
- [ ] Wrap `QueryHistory.tsx` list in `useVirtualizer` — render only visible rows
- [ ] Wrap `Citations.tsx` if citation count exceeds 20 (add a `virtualise` prop, off by default)
- [ ] ~~Wrap all TanStack Table instances in admin with row virtualization~~ — DROPPED: `@tanstack/react-table` was uninstalled (no imports in `frontend/src/`); admin tables are plain HTML tables. Revisit if a real table lib is reintroduced.

### S3 — Graph Scalability (medium ROI, medium effort)

The current WS stream sends the entire Neo4j graph. At 1,000+ nodes the canvas becomes unreadable and the stream takes seconds.

- [ ] Add `?team_id` filter to `WS /graph/stream` on the backend — only stream nodes/edges for the requesting team
- [ ] Add `?seed_entities` param: stream only the N-hop neighbourhood of entities mentioned in the current query answer (parsed from SSE `agent_done` chunk metadata)
- [ ] Add zoom-to-fit button on `KnowledgeGraph.tsx`: calls `graphRef.current.zoomToFit(400)`
- [ ] Add label toggle: hide node name labels below a configurable zoom threshold (`graphRef.current.nodeLabel(...)`)
- [ ] Add edge type filter: checkboxes to show/hide by `rel` type (DEPENDS_ON, CAUSED_BY, etc.)

### S4 — Bundle Splitting & Performance (medium ROI, medium effort)

Current concern: `force-graph` and `recharts` are large. Both are already lazily imported/loaded, but chunk boundaries need review.

- [ ] Run `pnpm build` and inspect `dist/` chunk sizes; `force-graph` and `recharts` should each be in their own async chunk
- [ ] Add `React.lazy` + `Suspense` around `KnowledgeGraph` (already uses dynamic `import('force-graph')` inside useEffect, but the component itself is not lazy — add lazy wrapper in `routes.ts`)
- [ ] Add `vite-bundle-visualizer` to devDependencies for ongoing monitoring: `pnpm run build:analyze`
- [ ] Set `build.chunkSizeWarningLimit: 600` in `vite.config.ts` — fail CI if a chunk exceeds 600 KB

### S5 — Error Tracking (high ROI, low effort once backend is in prod)

- [ ] Add Sentry SDK: `@sentry/react` + `@sentry/vite-plugin`
- [ ] Wrap `ErrorBoundary` to call `Sentry.captureException` before rendering fallback UI
- [ ] Tag Sentry events with `user.id`, `user.team_id`, and `request_id` (from `ApiError.requestId`) so errors correlate with backend logs
- [ ] Add `Sentry.setTag('session_id', ...)` at query start so SSE errors link to the backend trace

### S6 — Feature Flags (medium ROI, low effort)

Admin and analytics features should be progressively enabled per team without a new deploy.

- [ ] Add a lightweight feature flag store in Zustand: `featureStore.ts` — maps flag names to booleans
- [ ] Fetch flags from `GET /api/admin/feature-flags` on app load (or from env vars for MVP)
- [ ] Gate `AdminPage`, `AnalyticsPage`, and `NotificationCenter` behind flags: `if (!flags.admin) return null`
- [ ] Add backend endpoint `GET /api/admin/feature-flags` returning `{analytics: bool, admin: bool, notifications: bool}` driven by `.env`

### S7 — Offline / PWA (low ROI now, high later)

Enterprise intranet deployments may have intermittent connectivity.

- [ ] Add `vite-plugin-pwa` with a network-first strategy for API calls and cache-first for static assets
- [ ] Cache the last 10 query results in IndexedDB via a `useQueryCache` hook — show stale results with a "Last updated X ago" banner when offline
- [ ] Show a persistent offline banner when `navigator.onLine === false` (listen to `window.addEventListener('offline', ...)`)

### S8 — Accessibility Audit (compliance requirement for enterprise)

- [ ] Run `axe-core` accessibility audit via `@axe-core/playwright` in E2E suite — zero critical violations required to pass CI
- [ ] `KnowledgeGraph` canvas: add `aria-label` with node/edge counts; add keyboard alternative to browse nodes (Tab cycles through nodes, Enter opens detail panel)
- [ ] All modals (Radix Dialog): confirm focus trap, `Escape` closes, `aria-labelledby` and `aria-describedby` set
- [ ] Colour-blind safe palette: add a second distinguishing property to graph nodes beyond colour (shape or border pattern) so the graph is readable without colour

### S9 — Internationalisation scaffold (future-proofing only)

Not needed for MVP but adding i18n later to an existing codebase is expensive if strings are hardcoded.

- [ ] Add `i18next` + `react-i18next` to dependencies
- [ ] Extract all user-visible strings from components into `public/locales/en/translation.json`
- [ ] Replace string literals with `t('key')` calls — start with high-traffic components (`SearchBox`, `Answer`, `Citations`, `LoadingSkeleton`)
- [ ] Do NOT localise error codes or log messages — those stay in English for support

### S10 — Storybook for Component Library (DX, medium effort)

As the team grows, shared components need an isolated development environment.

- [ ] Add `@storybook/react-vite` 
- [ ] Write stories for: `LoadingSkeleton`, `AgentBadges` (all states), `Answer` (with bash block, with tables), `Citations`, `HallucinationWarning`, `HealthCards` (ok/degraded/down states)
- [ ] Add Storybook visual diff via Chromatic (free tier) so component regressions are caught on PRs

---

## Key Rules

**Skeleton rule:** `LoadingSkeleton` must not render once `firstEventArrived` is true in `useSSEStream` OR `firstNodeArrived` is true in `useGraphStream`. One skeleton, gone on first signal.

**Bash rendering rule:** Fenced code blocks with language `bash`, `sh`, or `shell` get a copy button and shell syntax highlight in `Answer.tsx`.

**No page switches:** `ResultsPage` is the single page. The URL can update but the page never unmounts during an active query stream.

**SSE vs WebSocket:** `useSSEStream` uses `fetch()` (not `EventSource`) because we POST a body. `useGraphStream` uses native `WebSocket`.
