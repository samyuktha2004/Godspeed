from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_EXT_MAP: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "docx",
    ".xml": "xml",
    ".txt": "text",
    ".md": "text",
    ".markdown": "text",
    ".csv": "csv",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".html": "html",
    ".htm": "html",
}

_MIME_MAP: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "docx",
    "text/xml": "xml",
    "application/xml": "xml",
    "text/plain": "text",
    "text/markdown": "text",
    "text/csv": "csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xlsx",
    "text/html": "html",
}


def detect_format(path: str) -> str:
    """Return a normalized format string or 'unknown'."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext in _EXT_MAP:
        return _EXT_MAP[ext]

    # MIME fallback via python-magic (optional dep)
    try:
        import magic
        mime = magic.from_file(str(p), mime=True)
        if mime in _MIME_MAP:
            return _MIME_MAP[mime]
    except ImportError:
        pass
    except Exception:
        logger.debug("detector: magic failed for %s", path)

    logger.warning("detector: unknown format for %s", path)
    return "unknown"
