-- Documents table — one row per ingested document (PDF, Confluence page, GitHub file, Jira issue)
create table if not exists documents (
    id          uuid primary key default gen_random_uuid(),
    doc_id      text not null unique,
    title       text not null,
    source_url  text not null,
    source_type text not null,
    team_id     text not null,
    metadata    jsonb not null default '{}',
    last_commit_sha text,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create index if not exists documents_team_id_idx        on documents (team_id);
create index if not exists documents_source_type_idx    on documents (source_type);
create index if not exists documents_team_source_idx    on documents (team_id, source_type);
-- Lets the CAG job find repos for a team via metadata->>'repo' without a full scan
create index if not exists documents_metadata_gin_idx   on documents using gin (metadata);


-- Chunks table — one row per text chunk produced by the chunker
create table if not exists chunks (
    id          uuid primary key default gen_random_uuid(),
    chunk_id    text not null unique,
    doc_id      text not null references documents (doc_id) on delete cascade,
    text        text not null,
    source      text not null,
    source_type text not null,
    team_id     text not null,
    chunk_index integer not null,
    created_at  timestamptz not null default now()
);

create index if not exists chunks_doc_id_idx    on chunks (doc_id);
create index if not exists chunks_team_id_idx   on chunks (team_id);


-- Teams table — one row per tenant team
create table if not exists teams (
    team_id      text primary key,
    cag_snapshot text,
    snapshot_at  timestamptz,
    created_at   timestamptz not null default now()
);


-- Ingest jobs table — tracks Celery task state for the API
create table if not exists ingest_jobs (
    job_id          text primary key,
    celery_task_id  text not null,
    status          text not null default 'pending',
    source_type     text not null,
    team_id         text not null,
    chunks_ingested integer not null default 0,
    error           text,
    created_at      timestamptz not null default now(),
    completed_at    timestamptz
);

create index if not exists ingest_jobs_team_id_idx  on ingest_jobs (team_id);
create index if not exists ingest_jobs_status_idx   on ingest_jobs (status);


-- RLS: each team only sees its own documents and chunks
alter table documents  enable row level security;
alter table chunks     enable row level security;
alter table ingest_jobs enable row level security;

-- Service role bypasses RLS; these policies cover the anon / authenticated roles
create policy "team isolation — documents"
    on documents for all
    using (team_id = current_setting('app.team_id', true));

create policy "team isolation — chunks"
    on chunks for all
    using (team_id = current_setting('app.team_id', true));

create policy "team isolation — ingest_jobs"
    on ingest_jobs for all
    using (team_id = current_setting('app.team_id', true));
