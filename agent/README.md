# Enterprise Knowledge Copilot — Agent Module

LangGraph-based multi-agent RAG system with Gemini, Qdrant, BGE-M3, and streaming SSE.

## Architecture

```
POST /agent/query
       │
       ▼
  planner_node  (Gemini 2.5 Pro)
       │  ExecutionPlan
       ▼
 ┌─────┴──────────┐
 │                │       (parallel)
doc_search    ticket_lookup
 │    └──────────┘
 │  live_docs   (conditional)
 └──────────────┘
       │
  synthesiser_node  (Gemini 2.5 Pro, streaming)
       │
  guardrail_node   (Gemini 2.5 Flash)
       │
    done / escalate
```

### Two-level orchestration

1. **Planner** (Level 1): Gemini analyses the query and returns a structured `ExecutionPlan` — which agents to run and which can be parallelised.
2. **LangGraph** (Level 2): Executes the plan, running independent nodes concurrently via `asyncio`.

### Parallelism rules

- `doc_search` and `ticket_lookup` always run in parallel when both are needed.
- `live_docs` runs after `doc_search` only if confidence is low OR the query names an external library.
- Each agent node calls exactly one tool. No agent calls two tools.

### Confidence gating

After BGE reranker scoring:
- `≥ 0.6` → `high`
- `0.4–0.6` → `medium`  
- `< 0.4` → `low`

The synthesiser adjusts its tone and the guardrail applies stricter escalation at low confidence.

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy env file and fill in keys
cp .env.example .env
# Set at minimum: GOOGLE_API_KEY

# 3. Start Qdrant locally
docker run -p 6333:6333 qdrant/qdrant

# 4. Run the API
uvicorn main:app --reload
```

Your `main.py` should include:

```python
from fastapi import FastAPI
from agent.api import router

app = FastAPI()
app.include_router(router)
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | ✅ | Google AI Studio key |
| `QDRANT_HOST` | optional | Default: `localhost` |
| `QDRANT_PORT` | optional | Default: `6333` |
| `JIRA_BASE_URL` | optional | Enables ticket_lookup |
| `JIRA_API_TOKEN` | optional | Enables ticket_lookup |
| `FIRECRAWL_API_KEY` | optional | Enables live_docs |
| `TAVILY_API_KEY` | optional | Enables live_docs |

## BM25 index

`doc_search` expects a BM25 index at `data/bm25_index.pkl` as a pickle with:

```python
{
  "index": BM25Okapi(...),
  "corpus": ["doc text 1", "doc text 2", ...],
  "doc_ids": ["chunk_id_1", "chunk_id_2", ...]
}
```

If the file is missing, BM25 is silently skipped and only Qdrant vectors are used.

## Qdrant collection schema

Collection name: `knowledge_base`

```
dense vector:  name="dense",  size=1024
sparse vector: name="sparse"
payload:       chunk_id, text, source, source_type, team_id
```

Data is filtered by `team_id` on every query — teams see only their own documents.

## Adding a new agent

1. Add a new tool in `tools/my_tool.py` with `async def run_my_tool(query, team_id) -> list[RetrievedChunk]`.
2. Add `"my_tool"` to the `Literal` in `models.py → AgentTask.agent`.
3. Add a node function in `graph.py`:

```python
async def my_tool_node(state: KnowledgeGraphState) -> dict:
    await _push_event(queue, "agent_started", {"agent": "my_tool"})
    chunks = await run_my_tool(task_input, state.query_input.team_id)
    ...
```

4. Register the node and wire its edges in `build_graph()`.
5. Update `PLANNER_SYSTEM_PROMPT` in `prompts.py` to describe when to use the new agent.

## SSE event stream

Events emitted in order:

| Event | Payload |
|---|---|
| `plan_ready` | `{tasks, reasoning}` |
| `agent_started` | `{agent}` |
| `agent_done` | `{agent, chunks, confidence}` |
| `synthesis_started` | `{}` |
| `answer_chunk` | `{chunk}` (one per token) |
| `guardrail_result` | `{score, escalate}` |
| `done` | `{}` |
| `error` | `{message}` |
