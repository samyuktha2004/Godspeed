# Godspeed Setup Guide

## Prerequisites

- Python 3.11+
- Docker (for Qdrant)
- Redis (brew install redis)
- Supabase account
- Google AI Studio API key (Gemini)

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/samyuktha2004/Godspeed.git
cd GodSpeed
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 2. Start infrastructure

```bash
# Redis (macOS)
brew services start redis

# Qdrant
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill in:

```
GOOGLE_API_KEY=your-gemini-key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_EMAIL=you@your-org.com
JIRA_API_TOKEN=your-atlassian-token
CONFLUENCE_BASE_URL=https://your-org.atlassian.net
CONFLUENCE_EMAIL=you@your-org.com
CONFLUENCE_TOKEN=your-atlassian-token
CONFLUENCE_SPACES=YOUR_SPACE_KEY
```

### 4. Run Supabase schema

Open your Supabase project → SQL Editor → paste and run `supabase/schema.sql`.

Also run this to add the qdrant_id column:
```sql
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS qdrant_id text;
```

### 5. Start the server

```bash
uvicorn main:app --port 8000
```

### 6. Start Celery worker (optional, for background jobs)

```bash
celery -A ingestion.jobs.celery_app worker --loglevel=info
celery -A ingestion.jobs.celery_app beat --loglevel=info
```

## Testing the System

### Ingest Confluence
```bash
curl -X POST http://localhost:8000/confluence/sync/YOUR_SPACE_KEY
```

### Query the agent
```bash
curl -X POST http://localhost:8000/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is our deployment process?", "team_id": "default", "session_id": "s1"}'
```

## Troubleshooting

### Server won't start
- Check all env vars are set in `.env`
- Make sure Redis and Qdrant are running
- Run `python -c "import main"` to check for import errors

### Agent returns low confidence
- The knowledge base may not have enough relevant content
- Run a Confluence sync to ingest more pages
- Check Supabase chunks table has rows

### Qdrant connection refused
- Start Docker and run: `docker start qdrant`
- Or: `docker run -d --name qdrant -p 6333:6333 qdrant/qdrant`

### Supabase RLS error
- Use the `service_role` key, not the `anon` key

### First query is slow (30-60s)
- BGE-M3 and reranker models download on first use (~1.5GB total)
- Subsequent queries are fast (models cached in memory)
