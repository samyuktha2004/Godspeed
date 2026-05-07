src/
├── agents_app.py               # Combined FastAPI app: all 3 agent routers + Qdrant startup
│
├── jira_agent/                 # JIRA ingestion agent (IMPLEMENTED)
│   ├── __init__.py
│   ├── config.py               # JiraAgentConfig — JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN,
│   │                           #   JIRA_PROJECT_KEYS (csv), JIRA_WEBHOOK_SECRET, TEAM_ID
│   ├── adapter.py              # JiraAdapter — fetch_issue, fetch_all (JQL), fetch_incremental
│   │                           #   Basic auth (base64 email:api_token), ADF text extraction
│   ├── chunker.py              # chunk_jira_issue → chunk 0: issue body, chunks 1..N: comments
│   ├── pipeline.py             # ingest_issue / ingest_project → chunk → PII mask → embed → Qdrant
│   ├── tasks.py                # Celery: jira_process_issue (queue=critical), jira_sync_project (queue=polling)
│   ├── router.py               # FastAPI: POST /webhooks/jira, POST /jira/sync/{project_key}
│   └── test_run.py             # Mock + real runthrough; works without credentials
│
├── confluence_agent/           # Confluence ingestion agent (IMPLEMENTED)
│   ├── __init__.py
│   ├── config.py               # ConfluenceAgentConfig — BASE_URL, TOKEN, EMAIL,
│   │                           #   CONFLUENCE_SPACES (csv), CONFLUENCE_WEBHOOK_SECRET, TEAM_ID
│   ├── adapter.py              # ConfluenceAdapter — fetch_page, fetch_space, fetch_incremental (CQL)
│   ├── chunker.py              # chunk_confluence_page — BeautifulSoup heading-split + breadcrumbs
│   │                           #   [Space > Ancestor > Page] prefix on every chunk; tables = 1 chunk each
│   ├── pipeline.py             # ingest_page / ingest_space → chunk → PII mask → embed → Qdrant
│   ├── tasks.py                # Celery: confluence_process_page (critical), confluence_sync_space (polling),
│   │                           #   confluence_periodic_sync (beat, 60 min incremental sync)
│   ├── router.py               # FastAPI: POST /webhooks/confluence, POST /confluence/sync/{space_key}
│   └── test_run.py             # Mock + real runthrough; works without credentials
│
├── file_agent/                 # File ingestion agent (IMPLEMENTED)
│   ├── __init__.py
│   ├── config.py               # FileAgentConfig — FILE_WATCH_FOLDER, TEAM_ID, MAX_WORDS_PER_CHUNK
│   ├── detector.py             # detect_format(path) — extension map first, python-magic MIME fallback
│   ├── chunker.py              # chunk_file_content — word-window (400w) for text/section/xml_node;
│   │                           #   1 chunk per table; 1 chunk per row (CSV/XLSX)
│   ├── pipeline.py             # process_file(path) → detect → parse → chunk → PII mask → embed → Qdrant
│   ├── tasks.py                # Celery: file_process_task (queue=default)
│   ├── watcher.py              # watchdog FileWatcher — on_created/on_modified → file_process_task.delay()
│   ├── router.py               # FastAPI: POST /api/ingest/file (upload), POST /api/ingest/folder
│   ├── test_run.py             # Writes sample CSV/TXT/HTML → processes → verifies in Qdrant
│   └── parsers/
│       ├── __init__.py         # Parser registry — register decorator + dispatch(path, fmt)
│       ├── pdf.py              # pdfplumber text extract + pytesseract OCR fallback (pymupdf pixmap)
│       ├── docx.py             # python-docx paragraph + table blocks
│       ├── xml.py              # xml.etree recursive node extraction with tag_path
│       ├── csv.py              # pandas read_csv + ExcelFile; each row = 1 "row" block
│       └── html.py             # BeautifulSoup: strip script/style/nav; heading sections + table blocks
│
├── adapters/                   # Generic source adapters (pre-existing)
│   ├── __init__.py             # AdapterRegistry
│   ├── base.py                 # BaseSourceAdapter ABC (connect, fetch_all, fetch_incremental, fetch_by_query)
│   ├── web_scraper.py          # WebScraperAdapter — URL fetch + sitemap crawl
│   └── polling.py              # LogAggregatorAdapter, MetricsAdapter, ErrorTraceAdapter, BusinessDataAdapter
│
├── integrations/               # Webhook handlers (pre-existing)
│   ├── __init__.py
│   └── webhooks.py             # WebhookValidator, JiraWebhookHandler, SlackWebhookHandler, GitHubWebhookHandler
│
├── ingestion/                  # Ingestion orchestrator (pre-existing)
│   ├── __init__.py
│   └── orchestrator.py         # IngestionOrchestrator — lock + sync state + _process_document
│
├── tasks/                      # Celery task stubs (pre-existing)
│   ├── __init__.py
│   └── ingestion_tasks.py      # scrape_url, scrape_sitemap (stub tasks)
│
├── redis/                      # Redis utilities (pre-existing)
│   ├── __init__.py
│   ├── cache.py                # SyncStateCache, CredentialCache
│   ├── queues.py               # IngestQueue, Priority enum
│   ├── session_state.py        # WebhookProcessingState (idempotency)
│   └── locks.py                # DistributedLock
│
├── celery_app.py               # src/ Celery app (priority queues: critical/high/default/polling/low)
│                               # NOTE: agent tasks run on ingestion.jobs.celery_app, not this one
└── config.py                   # Settings with IntegrationSettings (Jira, GitHub, Slack credentials)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ingestion/                      # Core RAG pipeline (DO NOT MODIFY — shared by all agents)
├── config.py                   # IngestionSettings — Qdrant, BGE-M3, GLiNER, Redis, spaCy config
├── models.py                   # RawDocument, DocumentChunk, EmbeddedChunk (Pydantic)
├── pipeline/
│   ├── embedder.py             # BGE-M3 singleton — embed_chunks() → list[EmbeddedChunk]
│   ├── pii_masker.py           # GLiNER singleton — mask_pii(text), mask_chunks(texts)
│   └── chunker.py              # spaCy sentence chunker — chunk_document() (used as fallback)
├── sources/
│   ├── base.py                 # BaseSource ABC
│   ├── confluence.py           # Legacy basic Confluence source (superseded by confluence_agent)
│   └── jira.py                 # Legacy stub Jira source (superseded by jira_agent)
├── storage/
│   └── qdrant_store.py         # ensure_collection_exists, upsert_chunks, delete_chunks_for_doc
└── jobs/
    ├── celery_app.py           # Ingestion Celery app — agent tasks register here
    ├── ingest_job.py           # run_ingest task (full pipeline: source → chunk → embed → Qdrant + Supabase)
    └── cag_job.py              # run_cag nightly beat task

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Startup commands:

  # Webhook + sync API server
  uvicorn src.agents_app:app --port 8001 --reload

  # Celery worker (ingestion pipeline — picks up all agent tasks)
  celery -A ingestion.jobs.celery_app worker -Q critical,default,polling -l info

  # Celery beat scheduler (confluence 60min periodic sync + cag nightly)
  celery -A ingestion.jobs.celery_app beat -l info

  # Test each agent (needs Qdrant running; works without real API credentials)
  python -m src.jira_agent.test_run
  python -m src.confluence_agent.test_run
  python -m src.file_agent.test_run

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Webhook registration (external, one-time setup):

  JIRA (Jira Cloud admin → System → WebHooks):
    URL:    https://your-server.com/webhooks/jira
    Events: issue_created, issue_updated

  Confluence (Confluence Cloud → General Config → Webhooks):
    URL:    https://your-server.com/webhooks/confluence
    Events: page_created, page_updated

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
New environment variables (add to .env):

  # JIRA Agent
  JIRA_EMAIL=bot@yourcompany.com
  JIRA_WEBHOOK_SECRET=your_secret
  JIRA_PROJECT_KEYS=BACKEND,INFRA

  # Confluence Agent
  CONFLUENCE_WEBHOOK_SECRET=your_secret
  CONFLUENCE_SPACES=ENG,PROD

  # File Agent
  FILE_WATCH_FOLDER=./data_sources
  TEAM_ID=default

  # Existing (already in ingestion/config.py)
  JIRA_BASE_URL, JIRA_API_TOKEN, CONFLUENCE_BASE_URL, CONFLUENCE_TOKEN, CONFLUENCE_EMAIL
  QDRANT_HOST, QDRANT_PORT, REDIS_URL
