from __future__ import annotations

from src.file_agent.parsers import Block, register


@register("text")
def parse_text(path: str) -> list[Block]:
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read().strip()
    if not content:
        return []
    return [{"type": "text", "content": content}]
