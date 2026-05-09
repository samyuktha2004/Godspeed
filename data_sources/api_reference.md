# Godspeed API Reference

## POST /agent/query

The main chat endpoint. Returns a Server-Sent Events (SSE) stream.

**Request body:**
```json
{
  "query": "What caused the last incident?",
  "team_id": "default",
  "session_id": "unique-session-id"
}
```

**SSE Events:**

| Event | Data | Description |
|-------|------|-------------|
| plan_ready | {tasks, reasoning} | Planner's execution plan |
| agent_started | {agent} | A retrieval agent has started |
| agent_done | {agent, chunks, confidence} | Agent finished, chunks found |
| synthesis_started | {} | Synthesiser is generating the answer |
| answer_chunk | {chunk} | One token/phrase of the answer |
| guardrail_result | {score, escalate} | Safety score (0-1) |
| error | {message} | Something went wrong |
| done | {} | Stream complete |

**Confidence levels:**
- `high` — reranker score ≥ 0.6, answer is reliable
- `medium` — reranker score ≥ 0.4, answer may have gaps
- `low` — reranker score < 0.4, answer is best-effort

---

## POST /confluence/sync/{space_key}

Triggers a full sync of a Confluence space. Runs as a background Celery task.

```bash
curl -X POST http://localhost:8000/confluence/sync/ENG
```

**Response:**
```json
{"status": "accepted", "task_id": "abc123", "space_key": "ENG"}
```

---

## POST /jira/sync/{project_key}

Syncs all issues in a Jira project.

```bash
curl -X POST http://localhost:8000/jira/sync/BACKEND
```

---

## POST /api/ingest/file

Upload a file for ingestion. Supports: PDF, DOCX, DOC, CSV, XLSX, XLS, HTML, HTM, XML, TXT, MD.

```bash
curl -X POST http://localhost:8000/api/ingest/file \
  -F "file=@report.pdf" \
  -F "team_id=default"
```

**Response:**
```json
{"status": "accepted", "task_id": "xyz789", "filename": "report.pdf"}
```

---

## GET /ingest/jobs/{job_id}

Check the status of an ingestion job.

```bash
curl http://localhost:8000/ingest/jobs/abc123
```

**Response:**
```json
{
  "job_id": "abc123",
  "status": "completed",
  "chunks_ingested": 42,
  "source_type": "confluence",
  "team_id": "default"
}
```

Status values: `pending`, `running`, `completed`, `failed`

---

## GET /graph/traverse

Query the knowledge graph for related entities.

```bash
curl "http://localhost:8000/graph/traverse?entity_name=AuthService&entity_type=Service&team_id=default"
```

**Parameters:**
- `entity_name` — name of the entity to start from
- `entity_type` — one of: Service, Library, Incident, Team
- `team_id` — your team identifier

---

## POST /webhooks/jira

Receives Jira Cloud webhooks. Configure in Jira → Project Settings → Webhooks.

- URL: `https://your-domain.com/webhooks/jira`
- Events: Issue Created, Issue Updated
- Signs with HMAC-SHA256 using `JIRA_WEBHOOK_SECRET`

---

## POST /webhooks/confluence

Receives Confluence webhooks. Configure in Confluence → Space Settings → Integrations.

- URL: `https://your-domain.com/webhooks/confluence`
- Events: page_created, page_updated
- Signs with HMAC-SHA256 using `CONFLUENCE_WEBHOOK_SECRET`
