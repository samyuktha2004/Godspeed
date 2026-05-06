from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# Block type used throughout: {"type": str, "content": str, **optional_meta}
Block = dict

_registry: dict[str, Callable[[str], list[Block]]] = {}


def register(fmt: str):
    def decorator(fn: Callable[[str], list[Block]]):
        _registry[fmt] = fn
        return fn
    return decorator


def dispatch(path: str, fmt: str) -> list[Block]:
    parser = _registry.get(fmt)
    if parser is None:
        logger.warning("parsers: no parser registered for format %r", fmt)
        return []
    try:
        return parser(path)
    except Exception:
        logger.exception("parsers: parser %r failed for %s", fmt, path)
        return []


# Import parsers to trigger registration
from src.file_agent.parsers import pdf, docx, xml, csv, html  # noqa: F401, E402
