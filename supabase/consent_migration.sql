-- ============================================================
-- Consent Migration — adds a DPDPA consent timestamp to users.
--
-- Safe to run multiple times (idempotent).
-- Run AFTER rbac_migration.sql and owner_migration.sql.
-- ============================================================

-- Timestamp of the user's DPDPA consent acknowledgement.
-- null = consent not yet captured → frontend shows the consent popup.
alter table users add column if not exists dpdpa_consent_at timestamptz;
