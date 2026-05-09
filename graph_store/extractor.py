from __future__ import annotations

import asyncio
import json
import logging
from typing import Union

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from graph_store.config import settings
from graph_store.models import ExtractionResult

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an entity and relationship extractor for a technical knowledge graph.

Given a chunk of technical documentation, extract entities and relationships.

Entity types to extract:
- Service: microservices, APIs, backend servers, internal platforms
- Library: packages, dependencies, SDKs, frameworks — include version if mentioned
- Incident: incident IDs, outage references, post-mortem subjects
- Team: team names, squad names, group names

Relationship types to extract (use exact rel_type strings):
- (Chunk)-[MENTIONS]->(Service)
- (Chunk)-[REFERENCES]->(Library)
- (Service)-[DEPENDS_ON]->(Library)
- (Service)-[OWNED_BY]->(Team)
- (Incident)-[CAUSED_BY]->(Service)
- (Incident)-[OWNED_BY]->(Team)

Rules:
- Only extract entities EXPLICITLY named in the text. Never infer or hallucinate.
- For libraries: look for import statements, package names, version numbers, deprecation notices.
- Return empty lists if nothing is found — this is correct and expected.
- from_name and to_name must match the name of an entity you extracted above.

Return ONLY valid JSON. No preamble. No markdown code fences.

Schema:
{
  "entities": [
    {"label": "Service|Library|Incident|Team", "name": "...", "version": null, "properties": {}}
  ],
  "relationships": [
    {"from_label": "...", "from_name": "...", "rel_type": "...", "to_label": "...", "to_name": "..."}
  ]
}"""

_EMPTY_RESULT = ExtractionResult()


def _make_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=settings.graph_extraction_model,
        google_api_key=settings.google_api_key,
        temperature=0.0,
    )


async def _extract_one(llm: ChatGoogleGenerativeAI, text: str) -> ExtractionResult:
    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=f"Text:\n{text}")]
    try:
        response = await llm.ainvoke(messages)
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[: raw.rfind("```")]
        data = json.loads(raw)
        return ExtractionResult(**data)
    except Exception:
        logger.exception("extractor: failed to parse Gemini response for chunk — returning empty")
        return _EMPTY_RESULT


async def extract_batch(texts: list[str]) -> list[ExtractionResult]:
    if not texts:
        return []

    llm = _make_llm()
    batch_size = settings.graph_extraction_batch_size
    results: list[ExtractionResult] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        batch_results = await asyncio.gather(
            *[_extract_one(llm, text) for text in batch],
            return_exceptions=False,
        )
        results.extend(batch_results)
        logger.debug(
            "extractor: processed batch %d-%d of %d",
            start,
            start + len(batch),
            len(texts),
        )

    return results
