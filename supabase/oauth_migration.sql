-- OAuth2 / SSO migration
-- Adds Google OAuth identity columns to the users table.
-- Run once in the Supabase SQL Editor (or via `supabase db push`).

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS oauth_provider text,
  ADD COLUMN IF NOT EXISTS oauth_sub      text;

-- Unique constraint: one entry per (provider, provider_user_id) pair.
-- Partial index so NULLs (password-only accounts) are excluded.
CREATE UNIQUE INDEX IF NOT EXISTS users_oauth_identity_idx
  ON users (oauth_provider, oauth_sub)
  WHERE oauth_sub IS NOT NULL;

-- Fast lookup by sub during login (priority-1 path in get_or_create_oauth_user).
CREATE INDEX IF NOT EXISTS users_oauth_sub_idx
  ON users (oauth_sub)
  WHERE oauth_sub IS NOT NULL;
