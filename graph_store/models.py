from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    label: Literal["Service", "Library", "Incident", "Team"]
    name: str
    version: Optional[str] = None
    properties: dict[str, Any] = Field(default_factory=dict)


class ExtractedRelationship(BaseModel):
    from_label: str
    from_name: str
    rel_type: str
    to_label: str
    to_name: str


class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)


class GraphIngestRequest(BaseModel):
    chunk_ids: list[str]
    team_id: str


class GraphTraverseRequest(BaseModel):
    type: Literal["incident", "service", "library"]
    name: str
    team_id: str
