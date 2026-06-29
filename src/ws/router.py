"""WebSocket endpoints: /ws (notifications) and /ws/logs (structured log tail)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import deque
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.auth.router import _get_session
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["ws"])

# ---------------------------------------------------------------------------
# Shared broadcast infrastructure
# ---------------------------------------------------------------------------

# Ring buffer of the last 200 log lines (populated by _WSLogHandler below)
_log_buffer: deque[str] = deque(maxlen=200)

# Connected log-tail WebSocket clients
_log_clients: set[asyncio.Queue] = set()

# Connected notification clients
_notification_clients: set[asyncio.Queue] = set()


# ---------------------------------------------------------------------------
# Python logging → WebSocket bridge
# ---------------------------------------------------------------------------

class _WSLogHandler(logging.Handler):
    """Push JSON-formatted log records to all connected /ws/logs clients."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            _log_buffer.append(msg)
            for q in list(_log_clients):
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    pass
        except Exception:
            self.handleError(record)


# Install the handler on the root logger once
_ws_handler = _WSLogHandler()
_ws_level = getattr(logging, os.environ.get("LOG_WS_LEVEL", "WARNING").upper(), logging.WARNING)
_ws_handler.setLevel(_ws_level)
# Use the JSON formatter from our logger if available
try:
    from src.utils.logger import _JsonFormatter  # type: ignore[attr-defined]
    _ws_handler.setFormatter(_JsonFormatter())
except Exception:
    _ws_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

logging.getLogger().addHandler(_ws_handler)


# ---------------------------------------------------------------------------
# WS /ws — notification stream
# ---------------------------------------------------------------------------

async def _ws_authenticate(websocket: WebSocket) -> dict | None:
    """Resolve user from gs_session cookie for a WebSocket connection.
    Returns the user dict, or None if the session is missing/invalid.
    """
    session_id = websocket.cookies.get("gs_session")
    if not session_id:
        cookie_header = websocket.headers.get("cookie", "")
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith("gs_session="):
                session_id = part[len("gs_session="):]
                break
    if not session_id:
        return None
    try:
        session = await _get_session(session_id)
        return session["user"] if session else None
    except Exception:
        return None


async def broadcast_notification(payload: dict[str, Any]) -> None:
    """Call this from anywhere to push a notification to all connected clients."""
    msg = json.dumps(payload)
    for q in list(_notification_clients):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    user = await _ws_authenticate(websocket)
    if not user:
        await websocket.close(code=4001, reason="Not authenticated")
        return

    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _notification_clients.add(q)
    logger.debug("ws_notifications_connected", extra={"client": str(websocket.client), "user": user.get("id")})
    try:
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=30)
                await websocket.send_text(msg)
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("ws_notifications_error", extra={"error": str(exc)})
    finally:
        _notification_clients.discard(q)


# ---------------------------------------------------------------------------
# WS /ws/logs — structured log tail
# ---------------------------------------------------------------------------

@router.websocket("/ws/logs")
async def logs_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    user = await _ws_authenticate(websocket)
    if not user:
        await websocket.close(code=4001, reason="Not authenticated")
        return
    if user.get("role") != "admin":
        await websocket.close(code=4003, reason="Admin access required")
        return

    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    _log_clients.add(q)

    # Replay buffered lines to new client
    for line in list(_log_buffer):
        try:
            q.put_nowait(line)
        except asyncio.QueueFull:
            break

    logger.debug("ws_logs_connected", extra={"client": str(websocket.client)})
    try:
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=30)
                await websocket.send_text(msg)
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text(json.dumps({"time": "", "level": "DEBUG", "logger": "ws", "request_id": "-", "message": "keepalive"}))
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("ws_logs_error", extra={"error": str(exc)})
    finally:
        _log_clients.discard(q)
