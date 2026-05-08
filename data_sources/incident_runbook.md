# Incident Runbook — Godspeed Platform

## INC-001: Qdrant Connection Refused

**Symptoms:** Agent queries return 0 chunks, logs show "Qdrant search failed"

**Root cause:** Qdrant Docker container stopped (usually after system restart)

**Resolution:**
```bash
docker ps -a | grep qdrant
docker start qdrant
curl http://localhost:6333/healthz  # should return "healthz check passed"
```

**Prevention:** Add Qdrant to Docker restart policy:
```bash
docker update --restart=always qdrant
```

---

## INC-002: Supabase RLS Policy Violation

**Symptoms:** Ingestion fails with "new row violates row-level security policy"

**Root cause:** Using anon key instead of service_role key in SUPABASE_KEY env var

**Resolution:**
1. Go to Supabase → Project Settings → API
2. Copy the `service_role` (secret) key
3. Update `.env`: `SUPABASE_KEY=<service_role_key>`
4. Restart the server

---

## INC-003: BGE-M3 Model OOM on Low-RAM Machine

**Symptoms:** Server crashes with MemoryError or process killed during first query

**Root cause:** BGE-M3 model requires ~4GB RAM. Machines with <8GB RAM may OOM.

**Resolution:**
- Upgrade to a machine with ≥16GB RAM for production
- For development: set `use_fp16=True` (already set) to halve memory usage
- Or reduce embed_batch_size in `.env`: `EMBED_BATCH_SIZE=8`

---

## INC-004: Celery Tasks Not Processing

**Symptoms:** Webhook triggers return "accepted" but chunks never appear in Supabase

**Root cause:** Celery worker not running

**Resolution:**
```bash
# Check if worker is running
ps aux | grep celery

# Start worker
celery -A ingestion.jobs.celery_app worker --loglevel=info

# Check Redis
redis-cli ping  # should return PONG
```

---

## INC-005: Jira Sync Returns 0 Issues

**Symptoms:** /jira/sync/{project} returns task accepted but 0 chunks stored

**Root cause options:**
1. Project has no issues yet
2. Wrong project key
3. API token expired or wrong email

**Resolution:**
```bash
# Verify auth
curl -u "your-email:your-token" \
  "https://your-org.atlassian.net/rest/api/3/myself"

# List available projects
curl -u "your-email:your-token" \
  "https://your-org.atlassian.net/rest/api/3/project/search"
```

---

## INC-006: Confluence Sync 404 Error

**Symptoms:** Confluence sync fails with "404 Not Found", URL has double `/wiki/wiki/`

**Root cause:** CONFLUENCE_BASE_URL incorrectly includes `/wiki` suffix

**Resolution:**
In `.env`, set:
```
CONFLUENCE_BASE_URL=https://your-org.atlassian.net
```
Not:
```
CONFLUENCE_BASE_URL=https://your-org.atlassian.net/wiki  ← WRONG
```
