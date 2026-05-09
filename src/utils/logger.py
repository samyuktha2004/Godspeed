"""Structured JSON logger for Godspeed backend.

Usage:
    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("graph_ingest_done", ingested=42, duration_ms=1230)

Every log line is a JSON object with at minimum:
  time, level, logger, request_id (from ContextVar), message, **extra_fields
"""
from __future__ import annotations

import json
import logging
import time
from contextvars import ContextVar
from typing import Any

# Set per-request by RequestLoggingMiddleware
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log: dict[str, Any] = {
            "time":       self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":      record.levelname,
            "logger":     record.name,
            "request_id": request_id_var.get(),
            "message":    record.getMessage(),
        }

        # Extra structured fields attached via logger.info("msg", extra={...})
        for key, val in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            }:
                log[key] = val

        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)

        return json.dumps(log, default=str)


def _configure_root() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)


_configure_root()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class Timer:
    """Context manager that measures elapsed ms."""

    def __init__(self) -> None:
        self._start = 0.0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        pass

    @property
    def ms(self) -> int:
        return int((time.perf_counter() - self._start) * 1000)
