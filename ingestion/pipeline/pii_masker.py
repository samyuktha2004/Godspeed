from __future__ import annotations

import logging
from typing import Optional

from gliner import GLiNER

from ingestion.config import settings

logger = logging.getLogger(__name__)

_PII_ENTITY_TYPES = [
    "person",
    "email",
    "phone",
    "ssn",
    "credit_card",
    "address",
    "date_of_birth",
]

_model: Optional[GLiNER] = None


def _get_model() -> GLiNER:
    global _model
    if _model is None:
        logger.info("pii_masker: loading GLiNER model %s", settings.gliner_model)
        _model = GLiNER.from_pretrained(settings.gliner_model)
    return _model


def mask_pii(text: str) -> str:
    try:
        model = _get_model()
        entities = model.predict_entities(text, _PII_ENTITY_TYPES, threshold=0.5)
        # iterate reverse so substring replacements don't shift later indices
        for ent in sorted(entities, key=lambda e: e["start"], reverse=True):
            text = text[: ent["start"]] + "[REDACTED]" + text[ent["end"] :]
        return text
    except Exception:
        logger.exception("pii_masker: masking failed; using original text")
        return text


def mask_chunks(texts: list[str]) -> list[str]:
    return [mask_pii(t) for t in texts]
