"""FastAPI router with SSE streaming endpoint for the knowledge copilot."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent.graph import graph
from agent.models import KnowledgeGraphState, QueryInput

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


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
        try:
            await graph.ainvoke(initial_state)
        except Exception as exc:
            logger.exception("Graph execution error for session=%s", query_input.session_id)
            await queue.put({"event": "error", "data": {"message": str(exc)}})
        finally:
            await queue.put(_SENTINEL)

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
async def query_endpoint(query_input: QueryInput) -> StreamingResponse:
    queue: asyncio.Queue = asyncio.Queue()
    logger.info(
        "query_endpoint: session=%s team=%s query=%r",
        query_input.session_id,
        query_input.team_id,
        query_input.query,
    )

    return StreamingResponse(
        _event_generator(query_input, queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
