# Godspeed Architecture

## System Components

### 1. Ingestion Pipeline

Documents flow through a 5-stage pipeline:

1. **Fetch** — Source adapters pull raw content (Confluence REST API, Jira REST API, GitHub API, file upload)
2. **Chunk** — Semantic chunker uses spaCy sentence boundaries to split into 512-token chunks with 15% overlap
3. **PII Mask** — GLiNER model redacts person names, emails, phone numbers, SSNs, credit cards, addresses
4. **Embed** — BGE-M3 produces 1024-dim dense vectors and sparse lexical weights per chunk
5. **Store** — Chunks upserted into Qdrant (vectors) and Supabase (metadata)

### 2. Agent Graph (LangGraph)

```
User Query
    │
    ▼
[planner_node] — Gemini 2.5 Pro decides which agents to invoke
    │
    ├──► [doc_search_node]    — Hybrid Qdrant search + BM25 + reranker
    ├──► [ticket_lookup_node] — Jira issue lookup
    └──► [live_docs_node]     — Live web fetch
    │
    ▼
[join_node] — Fan-in, waits for all retrieval agents
    │
    ▼
[synthesiser_node] — Gemini 2.5 Pro streams the answer with citations
    │
    ▼
[guardrail_node] — Gemini 2.5 Flash scores safety (0–1)
```

### 3. Retrieval (Hybrid Search)

For every query, doc_search runs three retrieval methods in parallel:
- **Dense search**: cosine similarity on 1024-dim BGE-M3 vectors
- **Sparse search**: lexical overlap using BGE-M3 sparse weights
- **BM25**: keyword matching on the full chunk corpus

Results are merged using Reciprocal Rank Fusion (RRF, k=60), then top candidates are reranked by BGE-reranker-v2-m3. Confidence is high (≥0.6), medium (≥0.4), or low (<0.4) based on the top reranker score.

### 4. Knowledge Graph (Neo4j)

After ingestion, Gemini Flash extracts entities and relationships from each chunk:
- **Entity types**: Service, Library, Incident, Team
- **Relationship types**: MENTIONS, REFERENCES, DEPENDS_ON, OWNED_BY, CAUSED_BY, DOCUMENTS, HAS_CHUNK

Graph is queryable via GET /graph/traverse.

### 5. CAG Snapshots

Every night at 2am UTC, a Celery beat task fetches recent Jira activity and GitHub commits for each team, summarises them with Gemini 2.5 Pro, and stores a 50k-token snapshot in the teams table. This snapshot is injected into the synthesiser context for time-aware answers.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /agent/query | SSE streaming chat query |
| POST | /ingest/confluence | Ingest a Confluence space |
| POST | /ingest/github | Ingest a GitHub repo |
| POST | /ingest/upload | Upload a PDF |
| GET  | /ingest/jobs/{id} | Check ingestion job status |
| POST | /confluence/sync/{space} | Sync a Confluence space |
| POST | /webhooks/confluence | Confluence webhook handler |
| POST | /jira/sync/{project} | Sync a Jira project |
| POST | /webhooks/jira | Jira webhook handler |
| POST | /api/ingest/file | Upload any file (PDF/DOCX/CSV/XLSX/HTML/XML) |
| POST | /api/ingest/folder | Ingest all files in a folder |
| POST | /graph/ingest | Re-run graph extraction for a team |
| GET  | /graph/traverse | Traverse the knowledge graph |

## Data Flow Diagram

```
Confluence ──┐
Jira        ──┤──► Ingestion Pipeline ──► Qdrant (vectors)
GitHub      ──┤                       ──► Supabase (metadata)
File Upload ──┘                       ──► Neo4j (graph)
                                      ──► BM25 index (pkl)
                                               │
User Query ──► LangGraph Agent Graph ──────────┘
                      │
                      ▼
              SSE Streaming Answer
```
