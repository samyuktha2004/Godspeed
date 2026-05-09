from __future__ import annotations

import hashlib
import logging

from ingestion.models import RawDocument
from ingestion.sources.base import BaseSource

logger = logging.getLogger(__name__)


class PDFSource(BaseSource):
    def __init__(self, team_id: str, filename: str, content: bytes) -> None:
        self._team_id = team_id
        self._filename = filename
        self._content = content

    def source_type(self) -> str:
        return "pdf"

    async def fetch(self) -> list[RawDocument]:
        try:
            import fitz
            doc = fitz.open(stream=self._content, filetype="pdf")
            pages_text: list[str] = []
            for page in doc:
                pages_text.append(page.get_text())
            doc.close()

            full_text = "\n\n".join(t for t in pages_text if t.strip())
            if not full_text.strip():
                logger.warning("pdf: no text extracted from %s", self._filename)
                return []

            doc_id = hashlib.sha256(self._content).hexdigest()
            title = self._filename.removesuffix(".pdf")
            return [
                RawDocument(
                    doc_id=doc_id,
                    title=title,
                    content=full_text,
                    source_url=self._filename,
                    source_type="pdf",
                    team_id=self._team_id,
                    metadata={"filename": self._filename, "pages": len(pages_text)},
                )
            ]
        except Exception:
            logger.exception("pdf: failed to parse %s", self._filename)
            return []
