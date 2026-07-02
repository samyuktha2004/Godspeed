# User Flows & Interface Specifications (Shipped)

> **Document purpose:** User journeys for each role (Engineer, Manager, Admin) for the flows that actually exist in the shipped frontend today. Cross-checked against [`PRD.md`](./PRD.md) and [`TODO.md`](./TODO.md).
>
> Flows that were part of the original UX vision but aren't built yet (onboarding tour, new-hire/intern mode, RBAC policy editor, API key management, data source OAuth wizard, user management UI, team workspaces) live in [`USERFLOW_VISION.md`](./USERFLOW_VISION.md) — check that doc before building any of those; some may already be superseded by a different, simpler approach, and some may no longer be needed.

---

## User Roles & Personas

### Engineer (primary user)

Queries the knowledge base when stuck. Needs fast, cited answers with follow-up links.

**Permissions:** Query all knowledge bases (RBAC-filtered), view personal query history, leave feedback.

### Manager

Monitors team query trends, knowledge gaps, and dependency risk via the Analytics dashboard.

**Permissions:** Access to the Analytics dashboard (Queries, Knowledge Health, Dependencies, Escalations tabs, per [`PRD.md`](./PRD.md#37-analytics-dashboard)).

### Admin

Configures data sources and monitors system health via the Admin panel.

**Permissions:** System Status, Data Sources (toggle on/off), System Logs, Ingest trigger — see [`PRD.md`](./PRD.md#38-admin-panel). Credentials for the two built-in personas (demo/admin) come from env vars; there is no user-management UI yet.

> **Note:** There is no differentiated "new hire" experience in the shipped product — everyone with the Engineer role sees the same UI regardless of tenure. See [`USERFLOW_VISION.md`](./USERFLOW_VISION.md) for the original new-hire onboarding design, which was never built.

---

## Engineer Flow: Query → Answer

```
Entry: SearchBox (⌘K) or Home page
    │
    ▼
[Results Page — Progressive Rendering]
├─ Loading skeleton until the first event from either stream arrives
│  (first SSE event from /agent/query OR first node from /graph/stream)
├─ Answer area: tokens stream in as SSE answer_chunk events arrive
├─ Knowledge graph canvas: nodes appear as WS node events arrive
├─ Citations: source name, type, relevance/reranker score, chunk preview
│  (overflow beyond 3 shown in "Related documents")
├─ Guardrail banner if confidence is low: "This answer may not be fully
│  accurate" + suggestion to verify sources
└─ Feedback buttons: [👍] [👎]
    │
    ▼ [User asks a follow-up]
    │
[Results Update]
├─ Previous answer stays visible; new answer appends with "Follow-up #N" label
├─ Same progressive loading as initial query
└─ NOTE: follow-ups don't carry conversation context yet — each is a fresh query (PRD known gap)
```

## Engineer Flow: Query History

```
Entry: Sidebar "History" link, or 6 most recent queries shown inline in the sidebar
    │
    ▼
[Query History Page] — GET /api/workspace/history?page=N&limit=20
├─ Query text, brief answer summary, timestamp, success/failure dot, duration
└─ [Ask again →] re-submits the exact query text
```

No bookmarking, no export, no copy-as-markdown yet (PRD known gaps).

---

## Manager Flow: Analytics Dashboard

Four tabs (see [`PRD.md`](./PRD.md#37-analytics-dashboard) for the authoritative spec):

| Tab | What it shows |
|---|---|
| **Queries** | Total queries, unique users, avg response time, success rate, daily trend chart |
| **Knowledge Health** | Coverage/freshness/accuracy per domain, radar chart (freshness/accuracy are currently hardcoded, not derived from real data — known gap) |
| **Dependencies** | Service/library nodes with version comparison, outdated/breaking-change flags |
| **Escalations** | Open/in-progress/resolved escalations table, filterable by status |

Export tab: CSV download of query events by date range. Date range filter: 7d / 30d / 90d / all.

No per-team settings page, no time-period comparison (this week vs last), and PDF export is a stub — see PRD known gaps.

---

## Admin Flow: System Panel

Three tabs (see [`PRD.md`](./PRD.md#38-admin-panel)):

| Tab | Feature |
|---|---|
| **System Status** | Live health cards for Neo4j, Redis, Qdrant (OK/error state) |
| **Data Sources** | Toggle integrations on/off (Jira, Confluence, GitHub, Slack), state persisted in Redis — this is a toggle list, not an add/configure wizard |
| **System Logs** | Live WebSocket log tail (`WS /ws/logs`), filter by level, search, pause/resume, 500-line ring buffer |
| **Ingest** | Trigger graph ingest or file upload |

No user management UI, no RBAC policy editor, no API key management, no live sync-progress indicator — see [`USERFLOW_VISION.md`](./USERFLOW_VISION.md) for the original design of these.

---

## Cross-Role: Feedback

```
[Results Page / Answer]
    │
    ▼ [User clicks 👍 or 👎]
    │
👍: POST /api/query/{id}/feedback { sentiment: "helpful" } → toast → button replaced with "Marked as helpful"
👎: inline form expands ("What was wrong?") → optional text →
    "Not helpful" or "Flag as hallucination" → toast on submit
```

Stored as `gs:feedback:{queryId}` in Redis, TTL 30 days. No aggregate feedback dashboard for managers yet.

---

## Real-Time Features

### Knowledge Graph (Progressive Streaming)

Two streams open simultaneously on query submit:

```
Stream 1: SSE POST /agent/query
  routing_ready → plan_ready → agent_started → answer_chunk (stream) → guardrail_result → done

Stream 2: WS /graph/stream (query-scoped, seeded from cited entities via GET /graph/traverse)
  first node → graph canvas appears → subsequent nodes/edges animate in → done event
```

No page switch or reload at any point; skeleton shown only if zero events have arrived from either stream. Node hover shows a tooltip; node click opens a side panel with related documents.

### Notifications (WebSocket)

`WS /ws` exists and the frontend has a notification bell/toast UI, but **no backend events currently push to it** — this is wired end-to-end on the frontend but has no producer yet (see [`PRD.md`](./PRD.md) known gaps and [`TODO.md`](./TODO.md)).

---

## Error Handling (matches PRD §3.10)

| Scenario | User sees |
|---|---|
| No results | "No results found for [query]" with suggested reformulations |
| Query timeout (>30s) | "The query took too long to respond..." + Retry button |
| Answer cut off mid-stream | "Answer may be incomplete — connection dropped mid-stream." + Retry |
| Graph stream lost | "Having trouble loading the knowledge graph — trying again (X of 5)…" |
| Low-confidence answer | "This answer may not be fully accurate. Verify against the cited sources." |
| Insufficient RBAC permissions | Results are silently filtered server-side; no separate "N hidden results" UI is confirmed built |

---

## Navigation

**Desktop (≥1024px):** Fixed left sidebar (240px expanded / 56px collapsed) — Home, Ask (⌘K), History, Analytics, Admin (admin only), theme toggle, account. See [`PRD.md`](./PRD.md#4-navigation--layout) for the full layout diagram.

**Mobile (<1024px):** Top NavBar; Graph/Answer as separate tabs on the results page (Graph is default; Answer tab is disabled until the first SSE event arrives).

## Accessibility & Responsiveness

- Dark mode toggle (Settings > Appearance)
- Breakpoints: Mobile (320px), Tablet (768px), Desktop (1024px+)
- No native mobile app; graphs are desktop-only, query interface works on tablet
