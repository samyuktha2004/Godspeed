-- ============================================================
-- RBAC Migration — adds workspaces, users, channels, and
-- per-role / per-user permission tables.
--
-- Safe to run multiple times (all statements are idempotent).
-- Run AFTER the base schema.sql.
-- ============================================================

-- ── Workspaces (company-level isolation) ────────────────────
create table if not exists workspaces (
    id         uuid        primary key default gen_random_uuid(),
    slug       text        not null unique,
    name       text        not null,
    created_at timestamptz not null default now()
);

-- Seed the default workspace that matches existing data
insert into workspaces (id, slug, name)
values ('00000000-0000-0000-0000-000000000001', 'default', 'Default Workspace')
on conflict (slug) do nothing;


-- ── Users (replaces hardcoded credentials) ──────────────────
create table if not exists users (
    id             uuid        primary key default gen_random_uuid(),
    workspace_id   uuid        not null references workspaces(id) on delete cascade,
    email          text        not null,
    name           text        not null,
    -- bcrypt hash; null = SSO-only account
    password_hash  text,
    -- engineer | manager | admin | org_admin
    role           text        not null default 'engineer',
    is_new_hire    boolean     not null default false,
    -- auto-clear new_hire flag after this date (null = never auto-clear)
    new_hire_until date,
    is_active      boolean     not null default true,
    invited_by     uuid        references users(id),
    created_at     timestamptz not null default now(),
    last_active_at timestamptz,
    unique(workspace_id, email)
);

create index if not exists users_workspace_email_idx on users (workspace_id, email);
create index if not exists users_role_idx            on users (role);


-- ── Extend existing teams table ──────────────────────────────
-- The base schema has teams(team_id text PK, cag_snapshot, snapshot_at, created_at).
-- We add workspace linkage and display fields.
alter table teams add column if not exists workspace_id uuid references workspaces(id) on delete cascade;
alter table teams add column if not exists name         text;
alter table teams add column if not exists slug         text;

-- Backfill the default team row
update teams
   set workspace_id = '00000000-0000-0000-0000-000000000001',
       name         = 'Engineering',
       slug         = 'engineering'
 where team_id = 'default';


-- ── User → Team memberships ──────────────────────────────────
create table if not exists user_teams (
    user_id  uuid not null references users(id)         on delete cascade,
    team_id  text not null references teams(team_id)    on delete cascade,
    -- member | lead
    role     text not null default 'member',
    primary key (user_id, team_id)
);


-- ── Channels (scoped data sources within a workspace/team) ───
-- Examples: "Backend Confluence", "HR Payroll Docs", "Public GitHub"
create table if not exists channels (
    id           uuid        primary key default gen_random_uuid(),
    workspace_id uuid        not null references workspaces(id) on delete cascade,
    -- null = workspace-wide channel (not team-specific)
    team_id      text        references teams(team_id) on delete set null,
    name         text        not null,
    source_type  text,       -- github | confluence | notion | slack | file | url | null
    -- public | internal | confidential | restricted
    sensitivity  text        not null default 'internal',
    created_at   timestamptz not null default now()
);

create index if not exists channels_workspace_idx on channels (workspace_id);
create index if not exists channels_team_idx      on channels (team_id);

-- Seed the default channel that covers all existing 'default' team_id data
insert into channels (id, workspace_id, team_id, name, source_type, sensitivity)
values (
    '00000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000001',
    'default',
    'General',
    null,
    'internal'
)
on conflict do nothing;


-- ── Role-level channel access defaults ───────────────────────
-- Defines which roles can access a channel without an explicit override.
create table if not exists channel_role_grants (
    channel_id uuid not null references channels(id) on delete cascade,
    role       text not null,
    primary key (channel_id, role)
);

-- All roles can access the default general channel
insert into channel_role_grants (channel_id, role) values
    ('00000000-0000-0000-0000-000000000002', 'engineer'),
    ('00000000-0000-0000-0000-000000000002', 'manager'),
    ('00000000-0000-0000-0000-000000000002', 'admin'),
    ('00000000-0000-0000-0000-000000000002', 'org_admin')
on conflict do nothing;


-- ── Per-user channel permission overrides ────────────────────
-- Grants or revokes a specific user's access to a channel,
-- overriding their role's default grant.
create table if not exists user_channel_permissions (
    user_id    uuid        not null references users(id)    on delete cascade,
    channel_id uuid        not null references channels(id) on delete cascade,
    can_read   boolean     not null default true,
    granted_by uuid        references users(id),
    granted_at timestamptz not null default now(),
    primary key (user_id, channel_id)
);


-- ── Add channel_id to existing document tables ───────────────
alter table documents add column if not exists channel_id uuid references channels(id) on delete set null;
alter table chunks    add column if not exists channel_id uuid references channels(id) on delete set null;

create index if not exists documents_channel_id_idx on documents (channel_id);
create index if not exists chunks_channel_id_idx    on chunks    (channel_id);

-- Backfill: existing rows with team_id='default' map to the default channel
update documents
   set channel_id = '00000000-0000-0000-0000-000000000002'
 where team_id = 'default' and channel_id is null;

update chunks
   set channel_id = '00000000-0000-0000-0000-000000000002'
 where team_id = 'default' and channel_id is null;


-- ── Audit log ────────────────────────────────────────────────
-- Append-only record of permission changes and sensitive admin actions.
create table if not exists rbac_audit_log (
    id          uuid        primary key default gen_random_uuid(),
    actor_id    uuid        references users(id),
    action      text        not null,   -- grant_channel | revoke_channel | change_role | invite_user | deactivate_user
    target_type text        not null,   -- user | channel | team
    target_id   text        not null,
    metadata    jsonb       not null default '{}',
    created_at  timestamptz not null default now()
);

create index if not exists rbac_audit_log_actor_idx  on rbac_audit_log (actor_id);
create index if not exists rbac_audit_log_target_idx on rbac_audit_log (target_type, target_id);
create index if not exists rbac_audit_log_time_idx   on rbac_audit_log (created_at desc);


-- ── RLS policies ─────────────────────────────────────────────
alter table users                   enable row level security;
alter table channels                enable row level security;
alter table user_channel_permissions enable row level security;
alter table rbac_audit_log          enable row level security;

-- Service role bypasses RLS; these cover anon/authenticated
-- Users can only see their own record (service role sees all)
create policy "users: own record only"
    on users for select
    using (id::text = current_setting('app.user_id', true));

-- Channels visible only if user has a role grant or explicit permission
create policy "channels: visible to granted users"
    on channels for select
    using (
        id in (
            select crg.channel_id
              from channel_role_grants crg
             where crg.role = current_setting('app.role', true)
        )
        or
        id in (
            select ucp.channel_id
              from user_channel_permissions ucp
             where ucp.user_id::text = current_setting('app.user_id', true)
               and ucp.can_read = true
        )
    );
