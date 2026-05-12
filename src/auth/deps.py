"""FastAPI auth dependencies — import these in any protected endpoint."""

from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException

from src.auth.router import _get_session


async def get_current_user(
    gs_session: str | None = Cookie(default=None),
) -> dict:
    """
    Resolve the authenticated user from the session cookie.

    Returns the user dict stored in the session, which includes:
        id, email, name, role, team_id, is_new_hire, allowed_channel_ids
    """
    if not gs_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await _get_session(gs_session)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")
    return session["user"]


def require_role(*roles: str):
    """
    Dependency factory that enforces the caller holds one of the given roles.

    Usage:
        @router.get("/admin/users")
        async def list_users(user = Depends(require_role("admin", "org_admin"))):
            ...
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.get('role')}' cannot access this endpoint",
            )
        return user
    return _check
