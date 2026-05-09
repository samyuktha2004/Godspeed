from __future__ import annotations

import logging

from src.file_agent.parsers import Block, register

logger = logging.getLogger(__name__)

_STRIP_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "aside"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


@register("html")
def parse_html(path: str) -> list[Block]:
    blocks: list[Block] = []
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("beautifulsoup4 not installed — cannot parse HTML")
        return blocks

    with open(path, encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()

    # Extract and remove tables
    for tbl_idx, table in enumerate(soup.find_all("table")):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"])]
            rows.append(cells)
        table.decompose()
        if rows:
            blocks.append({"type": "table", "content": rows, "table_index": tbl_idx})

    # Heading-based section split
    current_heading = ""
    current_parts: list[str] = []

    def _flush():
        text = " ".join(current_parts).strip()
        if text:
            blocks.append({"type": "section", "content": text, "heading": current_heading})

    body = soup.body or soup
    for el in body.children:
        if not hasattr(el, "name") or el.name is None:
            t = str(el).strip()
            if t:
                current_parts.append(t)
            continue
        if el.name in _HEADING_TAGS:
            _flush()
            current_heading = el.get_text(" ", strip=True)
            current_parts.clear()
        else:
            t = el.get_text(" ", strip=True)
            if t:
                current_parts.append(t)

    _flush()
    return blocks
