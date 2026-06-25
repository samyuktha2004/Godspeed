"""DB-backed user lookup and channel resolution for RBAC."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client():
    """Lazy singleton Supabase client — avoids import-time crash if not configured."""
    from supabase import create_client
    from src.config import settings
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError("Supabase not configured (SUPABASE_URL / SUPABASE_KEY missing)")
    return create_client(settings.supabase_url, settings.supabase_key)


def get_user_by_email(email: str) -> Optional[dict]:
    """Return user row from the users table, or None if not found / DB unavailable."""
    try:
        result = (
            _client()
            .table("users")
            .select("id, workspace_id, email, name, password_hash, role, is_owner, is_new_hire, is_active")
            .eq("email", email.lower())
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        logger.exception("auth_db: failed to look up user %s", email)
        return None


def get_allowed_channel_ids(user_id: str, role: str) -> list[str]:
    """
    Compute the channel IDs accessible to a user.

    Resolution order:
      1. Start with channels where the user's role is in channel_role_grants.
      2. Add channels where user has an explicit user_channel_permissions(can_read=True).
      3. Remove channels where user has user_channel_permissions(can_read=False) — explicit revoke.

    Returns a list of channel UUID strings.
    """
    try:
        sb = _client()

        # Channels accessible via role
        role_result = (
            sb.table("channel_role_grants")
            .select("channel_id")
            .eq("role", role)
            .execute()
        )
        role_channels: set[str] = {r["channel_id"] for r in role_result.data}

        # Per-user overrides
        override_result = (
            sb.table("user_channel_permissions")
            .select("channel_id, can_read")
            .eq("user_id", user_id)
            .execute()
        )
        explicitly_granted: set[str] = {r["channel_id"] for r in override_result.data if r["can_read"]}
        explicitly_revoked: set[str] = {r["channel_id"] for r in override_result.data if not r["can_read"]}

        allowed = (role_channels | explicitly_granted) - explicitly_revoked
        return list(allowed)

    except Exception:
        logger.exception("auth_db: failed to resolve channels for user %s", user_id)
        return []


def get_user_team_id(user_id: str) -> Optional[str]:
    """Return the primary team_id for a user (first membership row), or None."""
    try:
        result = (
            _client()
            .table("user_teams")
            .select("team_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return result.data[0]["team_id"] if result.data else None
    except Exception:
        logger.exception("auth_db: failed to get team for user %s", user_id)
        return None


_DEFAULT_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"

_OAUTH_USER_FIELDS = (
    "id, workspace_id, email, name, password_hash, role, is_owner, "
    "is_new_hire, is_active, oauth_provider, oauth_sub"
)


def get_or_create_oauth_user(email: str, name: str, oauth_sub: str) -> Optional[dict]:
    """Find or create a Supabase user for a Google OAuth login.

    Resolution order:
      1. Existing row matched by (oauth_provider='google', oauth_sub) — returning SSO user.
      2. Existing active row matched by email — links Google sub to a password account.
      3. No match — creates a new SSO-only user (password_hash=None).
    """
    try:
        sb = _client()

        # 1. Match by oauth_sub (fastest path for returning SSO users)
        result = (
            sb.table("users")
            .select(_OAUTH_USER_FIELDS)
            .eq("oauth_provider", "google")
            .eq("oauth_sub", oauth_sub)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]

        # 2. Match by email — link Google sub to an existing password-based account
        result = (
            sb.table("users")
            .select(_OAUTH_USER_FIELDS)
            .eq("email", email.lower())
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if result.data:
            user = result.data[0]
            sb.table("users").update({
                "oauth_provider": "google",
                "oauth_sub":      oauth_sub,
            }).eq("id", user["id"]).execute()
            user["oauth_provider"] = "google"
            user["oauth_sub"]      = oauth_sub
            logger.info("auth_db: linked google oauth to existing user %s", email)
            return user

        # 3. Create new SSO-only user (no password)
        insert_result = (
            sb.table("users")
            .insert({
                "workspace_id":   _DEFAULT_WORKSPACE_ID,
                "email":          email.lower(),
                "name":           name,
                "password_hash":  None,
                "role":           "engineer",
                "is_new_hire":    False,
                "oauth_provider": "google",
                "oauth_sub":      oauth_sub,
            })
            .execute()
        )
        logger.info("auth_db: created new oauth user %s", email)
        return insert_result.data[0] if insert_result.data else None

    except Exception:
        logger.exception("auth_db: get_or_create_oauth_user failed for %s", email)
        return None


def record_audit(
    actor_id: Optional[str],
    action: str,
    target_type: str,
    target_id: str,
    metadata: dict | None = None,
) -> None:
    """Append a row to rbac_audit_log. Fire-and-forget — never raises."""
    try:
        _client().table("rbac_audit_log").insert({
            "actor_id":    actor_id,
            "action":      action,
            "target_type": target_type,
            "target_id":   target_id,
            "metadata":    metadata or {},
        }).execute()
    except Exception:
        logger.warning("audit_log_failed: action=%s target=%s/%s", action, target_type, target_id)


# ---------------------------------------------------------------------------
# Default channel IDs for roles when DB is unavailable (dev fallback)
# These match the seeded rows in rbac_migration.sql
# ---------------------------------------------------------------------------
DEFAULT_CHANNEL_ID = "00000000-0000-0000-0000-000000000002"

ROLE_DEFAULT_CHANNELS: dict[str, list[str]] = {
    "engineer": [DEFAULT_CHANNEL_ID],
    "manager":  [DEFAULT_CHANNEL_ID],
    "admin":    [DEFAULT_CHANNEL_ID],
}
