"""Request logging middleware — attaches request_id to every log line."""
from __future__ import annotations

import uuid
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.utils.logger import Timer, get_logger, request_id_var

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = str(uuid.uuid4())
        token  = request_id_var.set(req_id)

        with Timer() as t:
            logger.info(
                "request_start",
                extra={
                    "method": request.method,
                    "path":   request.url.path,
                    "query":  str(request.url.query),
                },
            )
            try:
                response = await call_next(request)
            except Exception:
                logger.exception(
                    "request_unhandled_exception",
                    extra={"method": request.method, "path": request.url.path},
                )
                raise
            finally:
                request_id_var.reset(token)

        status = getattr(response, "status_code", 0)
        level  = logger.warning if status >= 400 else logger.info
        level(
            "request_end",
            extra={
                "method":      request.method,
                "path":        request.url.path,
                "status":      status,
                "duration_ms": t.ms,
            },
        )

        response.headers["X-Request-ID"] = req_id
        return response
