"""FastAPI router with SSE streaming endpoint for the knowledge copilot."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from uuid import uuid4
from src.utils.logger import Timer, get_logger as _get_logger
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from agent.graph import graph
from agent.models import KnowledgeGraphState, QueryInput
from src.auth.deps import get_current_user

logger = _get_logger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

HISTORY_KEY = "gs:queries"
TOPICS_KEY  = "gs:topics"


async def _store_query_event(
    query_input: QueryInput,
    duration_ms: int,
    success: bool,
    agent_results: dict | None = None,
    guardrail_score: float | None = None,
    escalated: bool = False,
    answer_text: str = "",
) -> None:
    """Persist query event to Redis for analytics and workspace history.

    Pipelined into a single roundtrip; intended to be invoked via
    ``asyncio.create_task`` so it never blocks the SSE close.
    """
    try:
        from src.utils.clients import get_redis

        brief = answer_text[:500].rstrip() if answer_text else ""
        if answer_text and len(answer_text) > 500:
            brief += "…"

        event = {
            "id":           str(uuid4()),
            "query":        query_input.query,
            "session_id":   query_input.session_id,
            "team_id":      query_input.team_id,
            "created_at":   datetime.utcnow().isoformat(),
            "success":      success,
            "duration_ms":  duration_ms,
            "answer_brief": brief,
            # Per-agent retrieval metrics — populated from final graph state
            "agents": {
                agent: {
                    "confidence":  result.retrieval_confidence,
                    "chunk_count": len(result.chunks),
                }
                for agent, result in (agent_results or {}).items()
            },
            "guardrail_score": guardrail_score,
            "escalated":       escalated,
        }

        topic_words = [
            w for w in query_input.query.lower().split()
            if len(w) > 4 and w.isalpha()
        ]

        escalation = None
        if escalated:
            escalation = {
                "id":              event["id"],
                "query":           query_input.query,
                "frequency":       1,
                "last_seen":       event["created_at"],
                "teams":           [query_input.team_id],
                "status":          "open",
                "gap_type":        "missing_knowledge",
                "guardrail_score": guardrail_score,
            }

        r = await get_redis()

        # Pipeline all Redis writes into one roundtrip — turns ~6 RTTs into 1.
        async with r.pipeline(transaction=False) as pipe:
            pipe.lpush(HISTORY_KEY, json.dumps(event))
            pipe.ltrim(HISTORY_KEY, 0, 999)
            for word in topic_words:
                pipe.zincrby(TOPICS_KEY, 1, word)
            if escalation is not None:
                pipe.lpush("gs:escalations", json.dumps(escalation))
                pipe.ltrim("gs:escalations", 0, 499)
            await pipe.execute()

        # Persist to Supabase for time-series anomaly detection.
        # Fire-and-forget: never allowed to fail the SSE stream.
        try:
            from src.anomaly.db import async_upsert_query_event

            async def _safe_upsert() -> None:
                try:
                    await asyncio.wait_for(async_upsert_query_event(event), timeout=5)
                except asyncio.TimeoutError:
                    logger.warning("anomaly_upsert_timeout", extra={"event_id": event.get("id")})
                except Exception as exc:  # noqa: BLE001 — analytics writes must not raise
                    logger.warning(
                        "anomaly_upsert_failed",
                        extra={"event_id": event.get("id"), "error": str(exc)},
                    )

            asyncio.create_task(_safe_upsert())
        except Exception as exc:
            logger.warning("anomaly_upsert_dispatch_failed", extra={"error": str(exc)})

    except Exception as exc:
        logger.warning("query_store_failed", extra={"error": str(exc)})


async def _event_generator(
    query_input: QueryInput,
    queue: asyncio.Queue,
) -> AsyncGenerator[str, None]:
    _SENTINEL = object()

    async def run_graph() -> None:
        initial_state = KnowledgeGraphState(
            query_input=query_input,
            sse_queue=queue,
        )
        success = False
        final_state: dict = {}
        with Timer() as t:
            try:
                final_state = await graph.ainvoke(initial_state)
                success = True
                logger.info(
                    "query_complete",
                    extra={"session_id": query_input.session_id, "duration_ms": t.ms},
                )
            except Exception as exc:
                logger.exception(
                    "query_error",
                    extra={"session_id": query_input.session_id, "duration_ms": t.ms, "error": str(exc)},
                )
                await queue.put({"event": "error", "data": {"message": str(exc)}})
            finally:
                # Close the SSE stream the moment the graph is done — analytics
                # writes run out-of-band so the client never waits on Redis.
                await queue.put(_SENTINEL)

        asyncio.create_task(
            _store_query_event(
                query_input, t.ms, success=success,
                agent_results=final_state.get("agent_results", {}) if success else {},
                guardrail_score=final_state.get("guardrail_score") if success else None,
                escalated=final_state.get("escalate", False) if success else False,
                answer_text=(final_state.get("final_answer") or "") if success else "",
            )
        )

    task = asyncio.create_task(run_graph())

    try:
        while True:
            item = await queue.get()
            if item is _SENTINEL:
                break

            event_name = item.get("event", "message")
            data_str = json.dumps(item.get("data", {}))
            yield f"event: {event_name}\ndata: {data_str}\n\n"

        yield "event: done\ndata: {}\n\n"

    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for session=%s", query_input.session_id)
        task.cancel()
        raise
    finally:
        if not task.done():
            task.cancel()


@router.post("/query")
async def query_endpoint(
    query_input: QueryInput,
    user: dict = Depends(get_current_user),
) -> StreamingResponse:
    # Enforce server-side team_id and channel IDs — never trust the client body.
    # Admins bypass RBAC channel filtering so they can search the full knowledge base.
    is_admin = user.get("role") in ("admin", "org_admin")
    query_input = query_input.model_copy(update={
        "team_id":             user.get("team_id", query_input.team_id),
        "allowed_channel_ids": [] if is_admin else user.get("allowed_channel_ids", []),
    })

    queue: asyncio.Queue = asyncio.Queue()
    logger.info(
        "query_start",
        extra={
            "session_id":   query_input.session_id,
            "team_id":      query_input.team_id,
            "channels":     len(query_input.allowed_channel_ids),
            "query_len":    len(query_input.query),
        },
    )

    return StreamingResponse(
        _event_generator(query_input, queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
