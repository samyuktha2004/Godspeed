"""Permission constants and role-to-permission mappings.

This module has no imports from other src.auth files, allowing both
deps.py and router.py to import from it without circular dependency.
"""

from __future__ import annotations


class Permission:
    # Search / query
    SEARCH = "search"

    # Analytics
    VIEW_OWN_ANALYTICS   = "view_own_analytics"
    VIEW_TEAM_ANALYTICS  = "view_team_analytics"
    VIEW_ANY_ANALYTICS   = "view_any_analytics"
    EXPORT_ANALYTICS     = "export_analytics"

    # Team management
    VIEW_TEAM_MEMBERS    = "view_team_members"
    MANAGE_TEAM_MEMBERS  = "manage_team_members"
    VIEW_TEAM_CHANNELS   = "view_team_channels"
    EDIT_TEAM_CHANNELS   = "edit_team_channels"
    VIEW_TEAM_SIGNALS    = "view_team_signals"
    RESOLVE_TEAM_SIGNALS = "resolve_team_signals"

    # Invites
    INVITE_USERS         = "invite_users"

    # Admin
    MANAGE_USERS         = "manage_users"
    MANAGE_CHANNELS      = "manage_channels"
    VIEW_ALL_SIGNALS     = "view_all_signals"
    RESOLVE_ALL_SIGNALS  = "resolve_all_signals"
    INGEST_DOCUMENTS     = "ingest_documents"
    TRIGGER_SYNC         = "trigger_sync"
    VIEW_WORKSPACE_HISTORY = "view_workspace_history"


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "engineer": {
        Permission.SEARCH,
        Permission.VIEW_OWN_ANALYTICS,
    },
    "manager": {
        Permission.SEARCH,
        Permission.VIEW_OWN_ANALYTICS,
        Permission.VIEW_TEAM_ANALYTICS,
        Permission.VIEW_TEAM_MEMBERS,
        Permission.MANAGE_TEAM_MEMBERS,
        Permission.VIEW_TEAM_CHANNELS,
        Permission.EDIT_TEAM_CHANNELS,
        Permission.VIEW_TEAM_SIGNALS,
        Permission.RESOLVE_TEAM_SIGNALS,
        Permission.INVITE_USERS,
    },
    "admin": {
        Permission.SEARCH,
        Permission.VIEW_OWN_ANALYTICS,
        Permission.VIEW_TEAM_ANALYTICS,
        Permission.VIEW_ANY_ANALYTICS,
        Permission.EXPORT_ANALYTICS,
        Permission.VIEW_TEAM_MEMBERS,
        Permission.MANAGE_TEAM_MEMBERS,
        Permission.VIEW_TEAM_CHANNELS,
        Permission.EDIT_TEAM_CHANNELS,
        Permission.VIEW_TEAM_SIGNALS,
        Permission.RESOLVE_TEAM_SIGNALS,
        Permission.INVITE_USERS,
        Permission.MANAGE_USERS,
        Permission.MANAGE_CHANNELS,
        Permission.VIEW_ALL_SIGNALS,
        Permission.RESOLVE_ALL_SIGNALS,
        Permission.INGEST_DOCUMENTS,
        Permission.TRIGGER_SYNC,
        Permission.VIEW_WORKSPACE_HISTORY,
    },
}


def permissions_for_role(role: str) -> list[str]:
    return sorted(ROLE_PERMISSIONS.get(role, set()))
