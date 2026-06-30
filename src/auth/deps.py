"""FastAPI auth dependencies — import these in any protected endpoint."""

from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException

from src.auth.router import _get_session
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def get_current_user(
    gs_session: str | None = Cookie(default=None),
) -> dict:
    """
    Resolve the authenticated user from the session cookie.

    Returns the user dict stored in the session, which includes:
        id, email, name, role, team_id, is_new_hire, allowed_channel_ids
    """
    if not gs_session:
        logger.warning("auth_missing_cookie")
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await _get_session(gs_session)
    if not session:
        logger.warning("auth_session_expired")
        raise HTTPException(status_code=401, detail="Session expired")
    return session["user"]


def require_role(*roles: str):
    """
    Dependency factory that enforces the caller holds one of the given roles.

    Usage:
        @router.get("/admin/users")
        async def list_users(user = Depends(require_role("admin"))):
            ...
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            logger.warning(
                "auth_role_denied",
                extra={"required_roles": list(roles), "actual_role": user.get("role"), "user_id": user.get("id")},
            )
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.get('role')}' cannot access this endpoint",
            )
        return user
    return _check


def require_permission(perm: str):
    """
    Dependency factory that enforces the caller holds a specific permission.

    Permissions are stored in the session under 'permissions' (list[str]).
    Usage:
        @router.post("/export")
        async def export(user = Depends(require_permission(Permission.EXPORT_ANALYTICS))):
            ...
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if perm not in user.get("permissions", []):
            logger.warning(
                "auth_permission_denied",
                extra={"permission": perm, "user_id": user.get("id")},
            )
            raise HTTPException(
                status_code=403,
                detail=f"Missing permission: {perm}",
            )
        return user
    return _check


def require_owner():
    """
    Dependency that enforces the caller is the workspace owner (is_owner=True).

    Usage:
        @router.delete("/workspace")
        async def delete_workspace(user = Depends(require_owner())):
            ...
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if not user.get("is_owner"):
            logger.warning("auth_owner_required", extra={"user_id": user.get("id")})
            raise HTTPException(
                status_code=403,
                detail="Only the workspace owner can perform this action",
            )
        return user
    return _check
