---
title: GodSpeed
emoji: 🚀
colorFrom: red
colorTo: yellow
sdk: docker
pinned: false
---


Deployment done at : https://huggingface.co/spaces/AdithyaVardan/GodSpeed

username : admin@godspeed.local
password : admin


# Godspeed

Enterprise Knowledge Copilot is a fully open-source, locally-compliant, agentic RAG platform that unifies internal and live external knowledge into a single cited, validated answer engine — purpose-built for IT enterprises operating under GDPR and India's DPDP Act.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.11+ | 3.12 recommended |
| pnpm | 9+ | `npm i -g pnpm` |
| Docker | 24+ | for Qdrant, Redis, Neo4j |
| Node.js | 20+ | required by pnpm |

---

## 1 — Clone and configure

```bash
git clone https://github.com/samyuktha2004/Godspeed.git
cd Godspeed
cp .env.example .env
```

Open `.env` and fill in every `<...>` placeholder.  
Minimum required keys for a first run:

```
GOOGLE_API_KEY=          # Gemini API key — all LLM calls route here
NEO4J_PASSWORD=          # choose any password; must match docker-compose below
SUPABASE_URL=            # your Supabase project URL
SUPABASE_KEY=            # service-role key (not anon) for backend writes
REDIS_URL=redis://localhost:6379/0
QDRANT_HOST=localhost
ALLOW_DEMO_AUTH=true     # enables demo/admin fallback login in local dev (default off)
```

> **Note:** `ALLOW_DEMO_AUTH` defaults to `false` so production deploys fail closed
> if Supabase is unreachable. Set it to `true` only for local dev.

For the frontend:

```bash
cp frontend/.env.example frontend/.env
# defaults (localhost:8000) are fine for local dev — no changes needed
```

---

## 2 — Start infrastructure

```bash
docker run -d --name qdrant  -p 6333:6333 qdrant/qdrant:latest
docker run -d --name redis   -p 6379:6379 redis:7-alpine
docker run -d --name neo4j   \
  -p 7474:7474 -p 7687:7687  \
  -e NEO4J_AUTH=neo4j/<your-NEO4J_PASSWORD> \
  neo4j:5
```

Wait ~10 seconds for Neo4j to finish its first-boot initialisation before continuing.

---

## 3 — Backend

```bash
# Install Python deps
pip install -r requirements.txt

# Download spaCy English model (required by chunking pipeline)
python -m spacy download en_core_web_sm
```

### Start the API server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI: http://localhost:8000/docs

### Start the Celery worker (ingestion tasks)

Open a second terminal:

```bash
celery -A src.celery_app worker -Q critical,default,polling -l info
```

### Start Celery beat (periodic Confluence sync — optional)

Open a third terminal:

```bash
celery -A ingestion.jobs.celery_app beat --loglevel=info
```

---

## 4 — Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

App: http://localhost:3000

---

## 5 — Verify the stack

### Health check

```bash
curl -s http://localhost:8000/health | python -m json.tool
```

### Post a query and stream the SSE response

```bash
curl -sN -X POST http://localhost:8000/agent/query \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"query":"What services does the auth team own?","team_id":"default","session_id":"test-001"}' \
  | while IFS= read -r line; do echo "$line"; done
```

Expected event sequence: `routing_ready` → `plan_ready` → `agent_started` (×N) → `agent_done` (×N) → `synthesis_started` → `answer_chunk` (×M) → `guardrail_result` → `done`

### Fetch knowledge graph nodes

```bash
curl -s "http://localhost:8000/graph/nodes?team_id=default&limit=20" | python -m json.tool
```

### Traverse the graph from a seed entity

```bash
curl -s -X POST http://localhost:8000/graph/traverse \
  -H "Content-Type: application/json" \
  -d '{"entity_id":"<node-id-from-above>","depth":2,"team_id":"default"}' \
  | python -m json.tool
```

### Stream graph via WebSocket

```bash
# Requires: npm i -g wscat
wscat -c "ws://localhost:8000/graph/stream?team_id=default"
```

### Trigger a manual file ingest

```bash
curl -s -X POST http://localhost:8000/ingest \
  -F "file=@/path/to/document.pdf" \
  -F "team_id=default" \
  | python -m json.tool
```

---

## 6 — Webhook setup (optional)

Each webhook endpoint verifies an HMAC-SHA256 signature. Generate secrets with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Set the generated value in `.env` (`JIRA_WEBHOOK_SECRET`, `CONFLUENCE_WEBHOOK_SECRET`), then register the corresponding URL in the Atlassian admin:

| Source | Endpoint |
|--------|----------|
| Jira | `POST /webhooks/jira` |
| Confluence | `POST /webhooks/confluence` |

GitHub and Slack have no ingestion webhooks — both are live on-demand lookup only via `POST /tools/chat` (see [`Docs/ARCHITECTURE.md`](Docs/ARCHITECTURE.md)).

---

## 7 — Project layout

```
Godspeed/
├── main.py                  # FastAPI entry point
├── agent/                   # LangGraph multi-agent orchestration
├── graph_store/             # Neo4j knowledge graph (extractor, writer, reader, API)
├── ingestion/               # Ingest pipeline + Celery jobs
├── src/
│   ├── confluence_agent/
│   ├── file_agent/
│   ├── jira_agent/
│   └── celery_app.py
├── toolsforgitnotionslack/  # GitHub / Slack / Notion agent
├── frontend/                # React 18 + TanStack Router + Vite
├── Docs/                    # Architecture, API contracts, TODO list
├── requirements.txt
└── .env.example
```

---

## 8 — Key environment variables reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `GOOGLE_API_KEY` | — | Gemini API — all LLM calls |
| `PLANNER_MODEL` | `gemini-2.5-flash` | Query planning agent — switch to `gemini-2.5-pro` for deeper reasoning at 5–10× latency |
| `SYNTHESISER_MODEL` | `gemini-2.5-flash` | Answer synthesis — same trade-off as planner |
| `SUMMARISER_MODEL` | `gemini-2.5-flash` | Document summarisation |
| `GUARDRAIL_MODEL` | `gemini-2.5-flash` | Output safety check |
| `GRAPH_EXTRACTION_MODEL` | `gemini-2.5-flash` | Neo4j entity extraction |
| `NEO4J_URI` | `bolt://localhost:7687` | Graph store |
| `QDRANT_HOST` | `localhost` | Vector store |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker + cache |
| `SUPABASE_URL` | — | Metadata storage |
| `TEAM_ID` | `default` | RBAC team scope |
| `ALLOW_DEMO_AUTH` | `false` | Enable demo/admin hardcoded login fallback (local dev only) |
| `COOKIE_SAMESITE` | `lax` | Session cookie SameSite — set `none` only when frontend is on a cross-site iframe (e.g. HF Spaces) |
| `COOKIE_SECURE` | `false` | Set `true` when serving over HTTPS in production |

Full variable list: [`.env.example`](.env.example)

---

## Docs

- [Architecture](Docs/ARCHITECTURE.md)
- [Tech Stack](Docs/TECHSTACK.md)
- [Input Methods](Docs/INPUTMETHODS.md)
- [User Flow](Docs/USERFLOW.md) ([original UX vision, not yet built](Docs/USERFLOW_VISION.md))
- [Frontend TODO](Docs/TODO.md)
