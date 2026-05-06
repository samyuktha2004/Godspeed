from __future__ import annotations

import asyncio
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class QueryInput(BaseModel):
    query: str
    team_id: str
    session_id: str


class AgentTask(BaseModel):
    agent: Literal["doc_search", "ticket_lookup", "live_docs", "summariser"]
    input: str
    depends_on: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    tasks: list[AgentTask]
    reasoning: str


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    source: str
    source_type: str
    score: float
    reranker_score: Optional[float] = None


class AgentResult(BaseModel):
    agent: str
    chunks: list[RetrievedChunk] = Field(default_factory=list)
    retrieval_confidence: Literal["high", "medium", "low"] = "low"
    error: Optional[str] = None


class KnowledgeGraphState(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    query_input: QueryInput
    execution_plan: Optional[ExecutionPlan] = None
    agent_results: dict[str, AgentResult] = Field(default_factory=dict)
    final_answer: Optional[str] = None
    citations: list[RetrievedChunk] = Field(default_factory=list)
    guardrail_passed: Optional[bool] = None
    guardrail_score: Optional[float] = None
    escalate: bool = False
    sse_queue: Any = None  # asyncio.Queue for streaming events


class SSEEvent(BaseModel):
    event: str
    data: Any
