from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

from src.file_agent.parsers import Block, register

logger = logging.getLogger(__name__)


def _iter_nodes(element: ET.Element, parent_path: str = "") -> list[Block]:
    blocks: list[Block] = []
    tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
    tag_path = f"{parent_path}/{tag}" if parent_path else tag
    text = (element.text or "").strip()
    if text:
        blocks.append({"type": "xml_node", "content": text, "tag_path": tag_path})
    for child in element:
        blocks.extend(_iter_nodes(child, tag_path))
    return blocks


@register("xml")
def parse_xml(path: str) -> list[Block]:
    try:
        tree = ET.parse(path)
        return _iter_nodes(tree.getroot())
    except Exception:
        logger.exception("xml_parser: failed to parse %s", path)
        return []
