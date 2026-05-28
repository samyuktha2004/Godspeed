"""Request middleware: per-request ID + logging, plus origin-based CSRF defense."""
from __future__ import annotations

import uuid
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

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


_STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _origin_host(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}".lower()


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Reject state-changing requests whose Origin/Referer is off-allowlist.

    Defense-in-depth against CSRF when SameSite=None is in effect (HF Spaces
    iframe deploy). Browsers attach Origin to all CORS preflights and to most
    cross-site fetch/XHR; Referer is the fallback for older form posts.

    Same-origin requests (no Origin header AND no Referer, or Origin matches the
    request host) are allowed through. Token-based auth callers (no cookie)
    skip the check — they're not subject to CSRF.
    """

    def __init__(self, app, allowed_origins: Iterable[str]) -> None:
        super().__init__(app)
        self._allowed = {o.lower().rstrip("/") for o in allowed_origins if o}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method not in _STATE_CHANGING_METHODS:
            return await call_next(request)

        # No session cookie → no CSRF surface (e.g. bearer-token API caller)
        if not request.cookies.get("gs_session"):
            return await call_next(request)

        origin  = _origin_host(request.headers.get("origin"))
        referer = _origin_host(request.headers.get("referer"))
        caller  = origin or referer

        if caller is None:
            # Same-origin form/XHR submissions from older browsers may omit both.
            # Allow through — SameSite=Lax still gates this case when configured.
            return await call_next(request)

        if caller.rstrip("/") in self._allowed:
            return await call_next(request)

        logger.warning(
            "csrf_origin_rejected",
            extra={"path": request.url.path, "origin": origin, "referer": referer},
        )
        return JSONResponse(
            status_code=403,
            content={"detail": "Cross-origin request rejected"},
        )
