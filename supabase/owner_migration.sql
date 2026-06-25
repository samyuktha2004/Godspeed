-- ============================================================
-- Owner Migration — collapses org_admin role into admin and
-- adds a transferable is_owner flag to the users table.
--
-- Safe to run multiple times (all statements are idempotent).
-- Run AFTER rbac_migration.sql.
-- ============================================================

-- 1. Add is_owner column (no-op if already exists)
alter table users add column if not exists is_owner boolean not null default false;

-- 2. Migrate existing org_admin users → admin + is_owner=true
update users
   set role     = 'admin',
       is_owner = true
 where role = 'org_admin';

-- 3. If the default workspace has no owner yet, crown the earliest admin
--    (covers fresh workspaces with no prior org_admin)
update users
   set is_owner = true
 where id = (
     select id from users
      where workspace_id = '00000000-0000-0000-0000-000000000001'
        and role         = 'admin'
        and is_active    = true
      order by created_at asc
      limit 1
 )
   and not exists (
     select 1 from users
      where workspace_id = '00000000-0000-0000-0000-000000000001'
        and is_owner     = true
   );

-- 4. Remove the now-obsolete org_admin channel-role grant
delete from channel_role_grants where role = 'org_admin';

-- 5. Index for fast owner lookups per workspace
create index if not exists users_workspace_owner_idx
    on users (workspace_id) where is_owner = true;
