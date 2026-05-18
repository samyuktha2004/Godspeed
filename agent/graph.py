"""LangGraph graph definition — nodes, edges, and parallel execution."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langgraph.graph import END, StateGraph

from agent.agents.guardrail import run_guardrail
from agent.agents.planner import run_planner
from agent.agents.synthesiser import stream_synthesis
from agent.models import AgentResult, KnowledgeGraphState, RetrievedChunk
from agent.tools.confluence_search import run_confluence_search
from agent.tools.doc_search import compute_retrieval_confidence, run_doc_search
from agent.tools.live_docs import run_live_docs
from agent.tools.slack_search import run_slack_search
from agent.tools.sql_query import run_sql_query
from agent.tools.ticket_lookup import run_ticket_lookup

logger = logging.getLogger(__name__)


async def _push_event(queue: asyncio.Queue, event: str, data: Any) -> None:
    if queue is not None:
        await queue.put({"event": event, "data": data})


async def planner_node(state: KnowledgeGraphState) -> dict:
    queue = state.sse_queue
    plan = await run_planner(state.query_input)
    await _push_event(
        queue,
        "plan_ready",
        {
            "tasks": [t.model_dump() for t in plan.tasks],
            "reasoning": plan.reasoning,
        },
    )
    return {"execution_plan": plan}


async def doc_search_node(state: KnowledgeGraphState) -> dict:
    queue = state.sse_queue
    await _push_event(queue, "agent_started", {"agent": "doc_search"})

    task_input = _find_task_input(state, "doc_search") or state.query_input.query
    chunks: list[RetrievedChunk] = []
    error: str | None = None

    try:
        chunks = await run_doc_search(
            task_input,
            state.query_input.team_id,
            state.query_input.allowed_channel_ids or None,
        )
    except Exception as exc:
        logger.exception("doc_search_node error")
        error = str(exc)

    confidence = compute_retrieval_confidence(chunks)
    result = AgentResult(
        agent="doc_search",
        chunks=chunks,
        retrieval_confidence=confidence,
        error=error,
    )
    await _push_event(
        queue,
        "agent_done",
        {"agent": "doc_search", "retrieval_confidence": confidence},
    )
    return {"agent_results": {**state.agent_results, "doc_search": result}}


async def ticket_lookup_node(state: KnowledgeGraphState) -> dict:
    queue = state.sse_queue
    await _push_event(queue, "agent_started", {"agent": "ticket_lookup"})

    task_input = _find_task_input(state, "ticket_lookup") or state.query_input.query
    chunks: list[RetrievedChunk] = []
    error: str | None = None

    try:
        chunks = await run_ticket_lookup(task_input, state.query_input.team_id)
    except Exception as exc:
        logger.exception("ticket_lookup_node error")
        error = str(exc)

    confidence = compute_retrieval_confidence(chunks)
    result = AgentResult(
        agent="ticket_lookup",
        chunks=chunks,
        retrieval_confidence=confidence,
        error=error,
    )
    await _push_event(
        queue,
        "agent_done",
        {"agent": "ticket_lookup", "retrieval_confidence": confidence},
    )
    return {"agent_results": {**state.agent_results, "ticket_lookup": result}}


async def confluence_search_node(state: KnowledgeGraphState) -> dict:
    queue = state.sse_queue
    await _push_event(queue, "agent_started", {"agent": "confluence_search"})

    task_input = _find_task_input(state, "confluence_search") or state.query_input.query
    chunks: list[RetrievedChunk] = []
    error: str | None = None

    try:
        chunks = await run_confluence_search(task_input, state.query_input.team_id)
    except Exception as exc:
        logger.exception("confluence_search_node error")
        error = str(exc)

    confidence = compute_retrieval_confidence(chunks)
    result = AgentResult(
        agent="confluence_search",
        chunks=chunks,
        retrieval_confidence=confidence,
        error=error,
    )
    await _push_event(queue, "agent_done", {"agent": "confluence_search", "retrieval_confidence": confidence})
    return {"agent_results": {**state.agent_results, "confluence_search": result}}


async def slack_search_node(state: KnowledgeGraphState) -> dict:
    queue = state.sse_queue
    await _push_event(queue, "agent_started", {"agent": "slack_search"})

    task_input = _find_task_input(state, "slack_search") or state.query_input.query
    chunks: list[RetrievedChunk] = []
    error: str | None = None

    try:
        chunks = await run_slack_search(task_input, state.query_input.team_id)
    except Exception as exc:
        logger.exception("slack_search_node error")
        error = str(exc)

    confidence = compute_retrieval_confidence(chunks)
    result = AgentResult(
        agent="slack_search",
        chunks=chunks,
        retrieval_confidence=confidence,
        error=error,
    )
    await _push_event(queue, "agent_done", {"agent": "slack_search", "retrieval_confidence": confidence})
    return {"agent_results": {**state.agent_results, "slack_search": result}}


async def live_docs_node(state: KnowledgeGraphState) -> dict:
    queue = state.sse_queue
    await _push_event(queue, "agent_started", {"agent": "live_docs"})

    task_input = _find_task_input(state, "live_docs") or state.query_input.query
    chunks: list[RetrievedChunk] = []
    error: str | None = None

    try:
        chunks = await run_live_docs(task_input, state.query_input.team_id)
    except Exception as exc:
        logger.exception("live_docs_node error")
        error = str(exc)

    confidence = compute_retrieval_confidence(chunks)
    result = AgentResult(
        agent="live_docs",
        chunks=chunks,
        retrieval_confidence=confidence,
        error=error,
    )
    await _push_event(
        queue,
        "agent_done",
        {"agent": "live_docs", "retrieval_confidence": confidence},
    )
    return {"agent_results": {**state.agent_results, "live_docs": result}}


async def sql_query_node(state: KnowledgeGraphState) -> dict:
    queue = state.sse_queue
    await _push_event(queue, "agent_started", {"agent": "sql_query"})

    task_input = _find_task_input(state, "sql_query") or state.query_input.query
    chunks: list[RetrievedChunk] = []
    error: str | None = None

    try:
        chunks = await run_sql_query(task_input, state.query_input.team_id)
    except Exception as exc:
        logger.exception("sql_query_node error")
        error = str(exc)

    confidence = compute_retrieval_confidence(chunks)
    result = AgentResult(
        agent="sql_query",
        chunks=chunks,
        retrieval_confidence=confidence,
        error=error,
    )
    await _push_event(
        queue,
        "agent_done",
        {"agent": "sql_query", "retrieval_confidence": confidence},
    )
    return {"agent_results": {**state.agent_results, "sql_query": result}}


async def synthesiser_node(state: KnowledgeGraphState) -> dict:
    queue = state.sse_queue
    await _push_event(queue, "synthesis_started", {})

    full_answer_parts: list[str] = []
    async for token in stream_synthesis(state.query_input.query, state.agent_results):
        full_answer_parts.append(token)
        await _push_event(queue, "answer_chunk", {"chunk": token})

    final_answer = "".join(full_answer_parts)

    all_chunks: list[RetrievedChunk] = []
    seen: set[str] = set()
    for result in state.agent_results.values():
        for chunk in result.chunks:
            if chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                all_chunks.append(chunk)

    await _push_event(queue, "citations", {"chunks": [c.model_dump() for c in all_chunks]})

    return {"final_answer": final_answer, "citations": all_chunks}


async def join_node(state: KnowledgeGraphState) -> dict:
    """Fan-in synchronisation point — waits for all retrieval nodes, then hands off to synthesiser."""
    await _push_event(state.sse_queue, "agent_started", {"agent": "synthesiser"})
    return {}


async def guardrail_node(state: KnowledgeGraphState) -> dict:
    queue = state.sse_queue
    score, escalate = await run_guardrail(
        state.final_answer or "",
        state.citations,
    )
    await _push_event(
        queue,
        "guardrail_result",
        {"score": score, "escalate": escalate},
    )
    return {
        "guardrail_passed": not escalate,
        "guardrail_score": score,
        "escalate": escalate,
    }


def _find_task_input(state: KnowledgeGraphState, agent: str) -> str | None:
    if state.execution_plan is None:
        return None
    for task in state.execution_plan.tasks:
        if task.agent == agent:
            return task.input
    return None


def _plan_includes(state: KnowledgeGraphState, agent: str) -> bool:
    if state.execution_plan is None:
        return False
    return any(t.agent == agent for t in state.execution_plan.tasks)


def _route_after_planner(state: KnowledgeGraphState) -> list[str]:
    if state.execution_plan is None:
        return ["synthesiser_node"]

    plan = state.execution_plan
    immediate: list[str] = []
    for task in plan.tasks:
        if not task.depends_on:
            immediate.append(f"{task.agent}_node")

    # If nothing is immediate (shouldn't happen), fall back to synthesiser
    return immediate or ["synthesiser_node"]


def _route_after_guardrail(state: KnowledgeGraphState) -> str:
    return "escalate" if state.escalate else END


def build_graph() -> Any:
    builder = StateGraph(KnowledgeGraphState)

    builder.add_node("planner_node", planner_node)
    builder.add_node("doc_search_node", doc_search_node)
    builder.add_node("ticket_lookup_node", ticket_lookup_node)
    builder.add_node("confluence_search_node", confluence_search_node)
    builder.add_node("slack_search_node", slack_search_node)
    builder.add_node("live_docs_node", live_docs_node)
    builder.add_node("sql_query_node", sql_query_node)
    builder.add_node("join_node", join_node)
    builder.add_node("synthesiser_node", synthesiser_node)
    builder.add_node("guardrail_node", guardrail_node)

    builder.set_entry_point("planner_node")

    builder.add_conditional_edges(
        "planner_node",
        _route_after_planner,
        {
            "doc_search_node": "doc_search_node",
            "ticket_lookup_node": "ticket_lookup_node",
            "confluence_search_node": "confluence_search_node",
            "slack_search_node": "slack_search_node",
            "live_docs_node": "live_docs_node",
            "sql_query_node": "sql_query_node",
            "summariser_node": "synthesiser_node",
            "synthesiser_node": "synthesiser_node",
        },
    )

    # Retrieval nodes all converge on join_node — LangGraph waits for every
    # incoming edge to fire before executing join_node (fan-in).
    builder.add_edge("doc_search_node", "join_node")
    builder.add_edge("ticket_lookup_node", "join_node")
    builder.add_edge("confluence_search_node", "join_node")
    builder.add_edge("slack_search_node", "join_node")
    builder.add_edge("live_docs_node", "join_node")
    builder.add_edge("sql_query_node", "join_node")

    builder.add_edge("join_node", "synthesiser_node")

    builder.add_edge("synthesiser_node", "guardrail_node")

    builder.add_conditional_edges(
        "guardrail_node",
        _route_after_guardrail,
        {END: END, "escalate": END},
    )

    return builder.compile()


graph = build_graph()
