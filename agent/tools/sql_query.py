"""NL-to-SQL query tool — translates natural language to a validated SELECT, executes via asyncpg."""

from __future__ import annotations

import logging
import re

from agent.agents._gemini import call_gemini_json
from agent.config import settings
from agent.models import RetrievedChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema context fed to the LLM for SQL generation
# ---------------------------------------------------------------------------

_SCHEMA_CONTEXT = """
documents:
  doc_id (text, unique), title (text), source_url (text),
  source_type (text: 'confluence'|'github'|'jira'|'file'|'url'),
  team_id (text), metadata (jsonb), created_at (timestamptz), updated_at (timestamptz)

chunks:
  chunk_id (text, unique), doc_id (text FK→documents.doc_id), text (text),
  source (text), source_type (text), team_id (text),
  chunk_index (integer), created_at (timestamptz)

ingest_jobs:
  job_id (text), status (text: 'pending'|'running'|'completed'|'failed'),
  source_type (text), team_id (text), chunks_ingested (integer),
  error (text nullable), created_at (timestamptz), completed_at (timestamptz nullable)
"""

SQL_NL_TO_SQL_PROMPT = """\
You are a SQL generation agent for an Enterprise Knowledge Copilot backed by PostgreSQL (Supabase).

Translate the user's natural language question into a safe SELECT query.

Available tables and columns:
{schema}

Rules:
1. Generate ONLY a SELECT statement — never INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or CREATE.
2. ALWAYS include `team_id = '<TEAM_ID_PLACEHOLDER>'` in every table's WHERE clause.
3. Use ONLY the tables listed above.
4. Always end with `LIMIT {max_rows}`.
5. Use COUNT(*), SUM, AVG, MAX, MIN for aggregations when the question asks for totals or stats.
6. For recency, use `created_at >= NOW() - INTERVAL '7 days'` style syntax.
7. Cast uuid columns with `::text` when displaying them.

Return ONLY valid JSON — no preamble, no markdown fences:
{{
  "sql": "<SELECT query — use '<TEAM_ID_PLACEHOLDER>' literally for every team_id value>",
  "description": "<one line describing what this query answers>"
}}"""

# ---------------------------------------------------------------------------
# Safety validation
# ---------------------------------------------------------------------------

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY|EXECUTE|CALL)\b",
    re.IGNORECASE,
)
_ALLOWED_TABLES = {"documents", "chunks", "ingest_jobs"}


def _validate_sql(sql: str) -> tuple[bool, str]:
    stripped = sql.strip()
    if not stripped.upper().startswith("SELECT"):
        return False, "only SELECT statements are permitted"

    m = _FORBIDDEN.search(sql)
    if m:
        return False, f"forbidden keyword: {m.group()}"

    referenced = re.findall(r"\bFROM\s+(\w+)", sql, re.IGNORECASE)
    referenced += re.findall(r"\bJOIN\s+(\w+)", sql, re.IGNORECASE)
    unknown = [t for t in referenced if t.lower() not in _ALLOWED_TABLES]
    if unknown:
        return False, f"unknown table(s): {unknown}"

    return True, ""


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


async def run_sql_query(
    query: str,
    team_id: str,
    allowed_channel_ids: list[str] | None = None,
) -> list[RetrievedChunk]:
    if not settings.effective_database_url:
        logger.warning("sql_query: DATABASE_URL / PG_DSN not configured — skipping")
        return []

    # --- Step 1: NL → SQL via Gemini Flash ---
    system_prompt = SQL_NL_TO_SQL_PROMPT.format(
        schema=_SCHEMA_CONTEXT,
        max_rows=settings.sql_max_rows,
    )
    try:
        result = await call_gemini_json(
            model_name=settings.summariser_model,
            system_prompt=system_prompt,
            user_message=f"Question: {query}",
        )
    except Exception:
        logger.exception("sql_query: NL-to-SQL translation failed")
        return []

    raw_sql: str = (result.get("sql") or "").strip()
    description: str = result.get("description") or "SQL query result"

    if not raw_sql:
        logger.warning("sql_query: Gemini returned empty SQL for query=%r", query)
        return []

    logger.info("sql_query: generated SQL=%r  desc=%r", raw_sql, description)

    # --- Step 2: Team-isolation check ---
    if "<TEAM_ID_PLACEHOLDER>" not in raw_sql:
        logger.warning("sql_query: LLM omitted team_id placeholder — refusing to execute")
        return []

    # Replace placeholder with positional parameter for asyncpg
    parameterized_sql = re.sub(r"'<TEAM_ID_PLACEHOLDER>'", "$1", raw_sql, count=1)

    # --- Step 3: Safety validation ---
    ok, reason = _validate_sql(parameterized_sql)
    if not ok:
        logger.warning("sql_query: SQL failed validation (%s): %s", reason, parameterized_sql)
        return []

    # --- Step 4: Execute ---
    try:
        import asyncpg  # imported lazily — only needed when tool is active

        conn = await asyncpg.connect(settings.effective_database_url)
        try:
            rows = await conn.fetch(parameterized_sql, team_id)
        finally:
            await conn.close()
    except Exception:
        logger.exception("sql_query: execution failed — sql=%s", parameterized_sql)
        return []

    # --- Step 5: Format results ---
    if not rows:
        return [
            RetrievedChunk(
                chunk_id="sql_result_empty",
                text=f"Query returned no results.\nDescription: {description}",
                source="sql_query",
                source_type="database",
                score=0.5,
                reranker_score=0.5,
            )
        ]

    columns = list(rows[0].keys())
    header = " | ".join(columns)
    separator = "-" * max(len(header), 10)
    body_lines = [" | ".join(str(row[c]) for c in columns) for row in rows]
    table_text = (
        f"{description}\n\n"
        f"{header}\n{separator}\n"
        + "\n".join(body_lines)
        + f"\n\n({len(rows)} row{'s' if len(rows) != 1 else ''})"
    )

    return [
        RetrievedChunk(
            chunk_id=f"sql_result_{abs(hash(table_text)) % 0xFFFFFF:06x}",
            text=table_text,
            source="sql_query",
            source_type="database",
            score=1.0,
            reranker_score=0.8,
        )
    ]
