from __future__ import annotations

import logging

from src.file_agent.parsers import Block, register

logger = logging.getLogger(__name__)


def _df_to_row_blocks(df) -> list[Block]:
    blocks: list[Block] = []
    for _, row in df.iterrows():
        parts = [f"{col}: {val}" for col, val in row.items() if str(val).strip()]
        if parts:
            blocks.append({"type": "row", "content": " | ".join(parts)})
    return blocks


@register("csv")
def parse_csv(path: str) -> list[Block]:
    try:
        import pandas as pd
        df = pd.read_csv(path, dtype=str).fillna("")
        return _df_to_row_blocks(df)
    except ImportError:
        logger.error("pandas not installed — cannot parse CSV")
        return []
    except Exception:
        logger.exception("csv_parser: failed to parse %s", path)
        return []


@register("xlsx")
def parse_xlsx(path: str) -> list[Block]:
    try:
        import pandas as pd
        xl = pd.ExcelFile(path)
        blocks: list[Block] = []
        for sheet_name in xl.sheet_names:
            df = xl.parse(sheet_name, dtype=str).fillna("")
            sheet_blocks = _df_to_row_blocks(df)
            for b in sheet_blocks:
                b["sheet"] = sheet_name
            blocks.extend(sheet_blocks)
        return blocks
    except ImportError:
        logger.error("pandas not installed — cannot parse XLSX")
        return []
    except Exception:
        logger.exception("xlsx_parser: failed to parse %s", path)
        return []
