from __future__ import annotations

import logging
from pathlib import Path

from src.file_agent.parsers import Block, register

logger = logging.getLogger(__name__)

_MIN_TEXT_CHARS = 50


@register("pdf")
def parse_pdf(path: str) -> list[Block]:
    blocks: list[Block] = []
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed — cannot parse PDF")
        return blocks

    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # Extract text
            text = page.extract_text() or ""
            if len(text.strip()) >= _MIN_TEXT_CHARS:
                blocks.append({"type": "text", "content": text, "page": page_num})
            else:
                # OCR fallback via pytesseract + pymupdf
                ocr_text = _ocr_page(path, page_num - 1)
                if ocr_text.strip():
                    blocks.append({"type": "text", "content": ocr_text, "page": page_num, "ocr": True})

            # Extract tables from pdfplumber
            for tbl_idx, table in enumerate(page.extract_tables() or []):
                rows = []
                for row in table:
                    cells = [str(c) if c else "" for c in (row or [])]
                    rows.append(cells)
                if rows:
                    blocks.append({"type": "table", "content": rows, "page": page_num, "table_index": tbl_idx})

    return blocks


def _ocr_page(path: str, page_index: int) -> str:
    try:
        import fitz  # pymupdf
        import pytesseract
        from PIL import Image
        import io

        doc = fitz.open(path)
        page = doc[page_index]
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img)
    except ImportError:
        logger.debug("pdf_parser: OCR deps (pymupdf/pytesseract/Pillow) not installed, skipping")
        return ""
    except Exception:
        logger.exception("pdf_parser: OCR failed for page %d", page_index)
        return ""
