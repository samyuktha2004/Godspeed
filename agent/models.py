from __future__ import annotations

import asyncio
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field


class QueryInput(BaseModel):
    # 10k chars is well above any reasonable user query and well below the
    # BGE-M3 / Gemini context limits. Prevents accidental/adversarial OOM on
    # the embedding model.
    query:      str = Field(..., min_length=1, max_length=10_000)
    team_id:    str
    session_id: str
    # Populated server-side from the auth session — never trusted from the client body.
    # Empty list = fall back to team_id-based filtering (legacy / dev mode).
    allowed_channel_ids: list[str] = Field(default_factory=list)


class AgentTask(BaseModel):
    agent: Literal["doc_search", "ticket_lookup", "confluence_search", "slack_search", "live_docs", "summariser", "sql_query"]
    input: str
    depends_on: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    tasks: list[AgentTask]
    reasoning: str


class RetrievalScope(BaseModel):
    """A narrowing filter the router applies BEFORE retrieval to cut cost/noise.

    Empty lists mean "no constraint on this dimension". A scope is only ever
    populated when the router is highly confident (soft-routing policy) — when
    unsure the router emits scope=None and retrieval stays broad, so a correct
    answer can never become unreachable.
    """
    source_types:  list[str] = Field(default_factory=list)   # e.g. ["confluence"]
    space_keys:    list[str] = Field(default_factory=list)    # Confluence space keys (payload: space_key)
    repos:         list[str] = Field(default_factory=list)    # GitHub repos (payload: repo)
    jira_projects: list[str] = Field(default_factory=list)    # agent-selection hint only (no Qdrant payload field)

    def is_empty(self) -> bool:
        return not (self.source_types or self.space_keys or self.repos or self.jira_projects)


class RoutingDecision(BaseModel):
    """Output of the deterministic router_node, consumed by the planner and
    threaded into retrieval as an additive Qdrant pre-filter."""
    scope: Optional[RetrievalScope] = None       # None => broad search (soft fallback)
    suggested_agents: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "low"
    reasoning: str = ""


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    source: str
    source_type: str
    score: float
    reranker_score: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    agent: str
    chunks: list[RetrievedChunk] = Field(default_factory=list)
    retrieval_confidence: Literal["high", "medium", "low"] = "low"
    error: Optional[str] = None


class KnowledgeGraphState(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    query_input: QueryInput
    routing_decision: Optional[RoutingDecision] = None
    execution_plan: Optional[ExecutionPlan] = None
    agent_results: Annotated[dict[str, AgentResult], lambda x, y: {**x, **y}] = Field(default_factory=dict)
    final_answer: Optional[str] = None
    citations: list[RetrievedChunk] = Field(default_factory=list)
    guardrail_passed: Optional[bool] = None
    guardrail_score: Optional[float] = None
    escalate: bool = False
    sse_queue: Any = None  # asyncio.Queue for streaming events


class SSEEvent(BaseModel):
    event: str
    data: Any
