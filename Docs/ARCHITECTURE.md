src/
├── adapters/                    # All source adapters
│   ├── __init__.py             # Registry + factory
│   ├── base.py                 # BaseSourceAdapter interface
│   ├── notion.py               # NotionAdapter
│   ├── confluence.py           # ConfluenceAdapter
│   ├── github.py               # GitHubAdapter
│   ├── slack.py                # SlackAdapter (NEW)
│   ├── jira.py                 # JiraAdapter
│   ├── logs.py                 # LogAggregatorAdapter (NEW)
│   ├── metrics.py              # MetricsAdapter (NEW)
│   ├── error_traces.py         # ErrorTraceAdapter (NEW)
│   ├── business_data.py        # BusinessDataAdapter (NEW)
│   ├── ocr.py                  # OCRAdapter (NEW)
│   └── pdf.py                  # PDFAdapter
│
├── integrations/               # Webhooks, event handlers, polling tasks
│   ├── __init__.py
│   ├── github/
│   │   ├── webhooks.py         # GitHub webhook handler
│   │   └── tasks.py            # GitHub Celery tasks
│   ├── slack/
│   │   ├── webhooks.py         # Slack event handler (NEW)
│   │   └── tasks.py            # Slack polling tasks (NEW)
│   ├── jira/
│   │   ├── webhooks.py         # Jira webhook handler (NEW)
│   │   └── tasks.py            # Jira polling tasks (NEW)
│   ├── logs/
│   │   ├── webhooks.py         # Error log webhook handler (NEW)
│   │   └── tasks.py            # Log polling tasks (NEW)
│   ├── metrics/
│   │   └── tasks.py            # Metrics polling tasks (NEW)
│   └── business_data/
│       └── tasks.py            # Business data sync tasks (NEW)
│
├── orm/                        # Database ORM connectors
│   ├── __init__.py
│   ├── base.py                 # BaseORM interface
│   ├── postgres.py             # PostgreSQL connector
│   ├── salesforce.py           # Salesforce REST API
│   ├── netsuite.py             # NetSuite SuiteTalk API
│   ├── sap.py                  # SAP OData API
│   └── generic_rest.py         # Generic REST API wrapper
│
├── tasks/                      # Celery task definitions (YOUR DOMAIN)
│   ├── __init__.py
│   ├── ingest_tasks.py         # Main ingest coordination
│   ├── sync_tasks.py           # Polling/incremental sync (notion, confluence, etc)
│   ├── webhook_tasks.py        # Handle webhook queuing (redis backed)
│   └── state_management.py     # Redis state tracking
│
├── redis/                      # Redis utilities (YOUR DOMAIN)
│   ├── __init__.py
│   ├── cache.py                # Caching layer (credentials, last_sync_times)
│   ├── queues.py               # Task queues (ingest queue, webhook queue)
│   ├── session_state.py        # Webhook/API session state
│   └── locks.py                # Distributed locks (prevent parallel syncs)
│
└── ingestion/
    ├── pipeline.py             # Main ingestion pipeline
    ├── enrichment.py           # Entity/relationship extraction
    └── orchestrator.py         # Routes docs through adapters

