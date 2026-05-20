-- ============================================================
-- Anomaly Detection Migration
-- Safe to run multiple times (all IF NOT EXISTS / ON CONFLICT).
-- Run AFTER rbac_migration.sql.
-- ============================================================

-- ── query_events: raw event persistence (90-day rolling window) ──────────────
CREATE TABLE IF NOT EXISTS query_events (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        text        NOT NULL UNIQUE,   -- same UUID as Redis event["id"]
    team_id         text        NOT NULL,
    session_id      text,
    success         boolean     NOT NULL DEFAULT true,
    duration_ms     integer,
    escalated       boolean     NOT NULL DEFAULT false,
    guardrail_score float,
    agent_metrics   jsonb       NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS qe_team_time_idx  ON query_events (team_id, created_at DESC);
CREATE INDEX IF NOT EXISTS qe_created_at_idx ON query_events (created_at DESC);
CREATE INDEX IF NOT EXISTS qe_escalated_idx  ON query_events (team_id, escalated, created_at DESC);

-- ── query_events_hourly: pre-aggregated hourly buckets ────────────────────────
CREATE TABLE IF NOT EXISTS query_events_hourly (
    team_id          text        NOT NULL,
    hour_bucket      timestamptz NOT NULL,
    query_count      integer     NOT NULL DEFAULT 0,
    escalation_count integer     NOT NULL DEFAULT 0,
    avg_duration_ms  integer,
    PRIMARY KEY (team_id, hour_bucket)
);

CREATE INDEX IF NOT EXISTS qeh_team_hour_idx ON query_events_hourly (team_id, hour_bucket DESC);

-- ── anomaly_signals: detected anomaly records ─────────────────────────────────
CREATE TABLE IF NOT EXISTS anomaly_signals (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id      text,
    signal_type  text        NOT NULL,
    -- query_spike | query_drop | escalation_trend | staleness | dependency_risk
    entity_type  text,
    entity_id    text,
    severity     text        NOT NULL DEFAULT 'medium',
    -- critical | high | medium | low
    score        float       NOT NULL DEFAULT 0.0,
    details      jsonb       NOT NULL DEFAULT '{}',
    resolved     boolean     NOT NULL DEFAULT false,
    resolved_by  uuid        REFERENCES users(id),
    resolved_at  timestamptz,
    detected_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS as_team_type_idx    ON anomaly_signals (team_id, signal_type, detected_at DESC);
CREATE INDEX IF NOT EXISTS as_severity_idx     ON anomaly_signals (severity, resolved, detected_at DESC);
CREATE INDEX IF NOT EXISTS as_resolved_idx     ON anomaly_signals (resolved, team_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS as_entity_idx       ON anomaly_signals (entity_type, entity_id);

-- RLS: all three tables are service-role only — no anon/authenticated policies
-- needed because all reads go through the FastAPI backend using the service key.
ALTER TABLE query_events          ENABLE ROW LEVEL SECURITY;
ALTER TABLE query_events_hourly   ENABLE ROW LEVEL SECURITY;
ALTER TABLE anomaly_signals       ENABLE ROW LEVEL SECURITY;

-- ── PostgreSQL function: in-DB hourly aggregation ────────────────────────────
-- Called via Supabase RPC so the worker never ships raw rows just to count them.
CREATE OR REPLACE FUNCTION aggregate_hourly_bucket(p_team_id text, p_hour timestamptz)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO query_events_hourly (team_id, hour_bucket, query_count, escalation_count, avg_duration_ms)
    SELECT
        p_team_id,
        p_hour,
        count(*)::integer,
        count(*) FILTER (WHERE escalated = true)::integer,
        avg(duration_ms)::integer
    FROM   query_events
    WHERE  team_id = p_team_id
      AND  date_trunc('hour', created_at AT TIME ZONE 'UTC') = p_hour
    ON CONFLICT (team_id, hour_bucket) DO UPDATE
        SET query_count      = EXCLUDED.query_count,
            escalation_count = EXCLUDED.escalation_count,
            avg_duration_ms  = EXCLUDED.avg_duration_ms;
END;
$$;
