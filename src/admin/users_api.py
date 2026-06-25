"""Admin REST endpoints — user management, channel management, and audit log."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.auth.deps import require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspace", tags=["admin-workspace"])

DEFAULT_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"


@lru_cache(maxsize=1)
def _client():
    """Lazy singleton Supabase service-role client."""
    from supabase import create_client
    from src.config import settings
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError("Supabase not configured (SUPABASE_URL / SUPABASE_KEY missing)")
    return create_client(settings.supabase_url, settings.supabase_key)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class CreateUserBody(BaseModel):
    email: str
    name: str
    role: str = "engineer"
    team_id: Optional[str] = None


class PatchUserBody(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    name: Optional[str] = None
    is_owner: Optional[bool] = None


@router.get("/users")
async def list_users(user=Depends(require_role("admin"))) -> dict:
    """List all users in the default workspace."""
    try:
        result = (
            _client()
            .table("users")
            .select("id, email, name, role, is_owner, is_active")
            .eq("workspace_id", DEFAULT_WORKSPACE_ID)
            .order("name")
            .execute()
        )
        return {"users": result.data}
    except Exception:
        logger.exception("admin: list_users failed")
        raise HTTPException(status_code=500, detail="Failed to fetch users")


@router.post("/users", status_code=201)
async def create_user(body: CreateUserBody, user=Depends(require_role("admin"))) -> dict:
    """Invite a new user — password_hash is left None; invite flow sets it later."""
    payload: dict = {
        "workspace_id":  DEFAULT_WORKSPACE_ID,
        "email":         body.email.lower(),
        "name":          body.name,
        "role":          body.role,
        "is_active":     True,
        "password_hash": None,
    }
    if body.team_id:
        payload["team_id"] = body.team_id

    try:
        result = _client().table("users").insert(payload).execute()
        return {"ok": True, "user": result.data[0] if result.data else None}
    except Exception:
        logger.exception("admin: create_user failed for %s", body.email)
        raise HTTPException(status_code=500, detail="Failed to create user")


@router.patch("/users/{user_id}")
async def patch_user(
    user_id: str,
    body: PatchUserBody,
    user=Depends(require_role("admin")),
) -> dict:
    """Update role, is_active, or name for a user.

    Changing is_owner requires the caller to be an owner themselves.
    Revoking the last owner's is_owner flag is blocked.
    Changing an owner's role to non-admin is blocked until is_owner is revoked.
    """
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        sb = _client()
        target_result = (
            sb.table("users")
            .select("is_owner, role")
            .eq("id", user_id)
            .eq("workspace_id", DEFAULT_WORKSPACE_ID)
            .limit(1)
            .execute()
        )
        target_row = target_result.data[0] if target_result.data else None
        if not target_row:
            raise HTTPException(status_code=404, detail="User not found")
    except HTTPException:
        raise
    except Exception:
        logger.exception("admin: patch_user pre-check failed for %s", user_id)
        raise HTTPException(status_code=500, detail="Failed to validate user")

    target_is_owner = bool(target_row.get("is_owner"))
    caller_is_owner = bool(user.get("is_owner"))

    # Only owners can grant or revoke is_owner
    if "is_owner" in updates:
        if not caller_is_owner:
            raise HTTPException(status_code=403, detail="Only workspace owners can change owner status")
        # Prevent revoking the last owner
        if updates["is_owner"] is False and target_is_owner:
            try:
                owner_count = (
                    sb.table("users")
                    .select("id", count="exact")
                    .eq("workspace_id", DEFAULT_WORKSPACE_ID)
                    .eq("is_owner", True)
                    .eq("is_active", True)
                    .execute()
                )
                if (owner_count.count or 0) <= 1:
                    raise HTTPException(
                        status_code=409,
                        detail="Cannot revoke the last owner — promote another admin first",
                    )
            except HTTPException:
                raise
            except Exception:
                logger.exception("admin: patch_user owner-count check failed")

    # Prevent changing an owner's role to non-admin while they still hold is_owner
    if updates.get("role") and updates["role"] != "admin" and target_is_owner:
        raise HTTPException(
            status_code=409,
            detail="Revoke owner status before changing the owner's role",
        )

    try:
        result = (
            sb.table("users")
            .update(updates)
            .eq("id", user_id)
            .eq("workspace_id", DEFAULT_WORKSPACE_ID)
            .execute()
        )
    except Exception:
        logger.exception("admin: patch_user failed for %s", user_id)
        raise HTTPException(status_code=500, detail="Failed to update user")

    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, user=Depends(require_role("admin"))) -> dict:
    """Soft-delete a user by setting is_active=False.

    Only owners can remove other owners. No one can remove themselves.
    The last owner cannot be removed.
    """
    if user_id == user["id"]:
        raise HTTPException(status_code=409, detail="Cannot remove yourself")

    try:
        sb = _client()
        target_result = (
            sb.table("users")
            .select("is_owner")
            .eq("id", user_id)
            .eq("workspace_id", DEFAULT_WORKSPACE_ID)
            .limit(1)
            .execute()
        )
        if not target_result.data:
            raise HTTPException(status_code=404, detail="User not found")
        target_is_owner = bool(target_result.data[0].get("is_owner"))
    except HTTPException:
        raise
    except Exception:
        logger.exception("admin: delete_user pre-check failed for %s", user_id)
        raise HTTPException(status_code=500, detail="Failed to deactivate user")

    if target_is_owner:
        if not user.get("is_owner"):
            raise HTTPException(
                status_code=403,
                detail="Only workspace owners can remove other owners",
            )
        # Block removing the last owner
        try:
            owner_count = (
                sb.table("users")
                .select("id", count="exact")
                .eq("workspace_id", DEFAULT_WORKSPACE_ID)
                .eq("is_owner", True)
                .eq("is_active", True)
                .execute()
            )
            if (owner_count.count or 0) <= 1:
                raise HTTPException(
                    status_code=409,
                    detail="Cannot remove the last owner — promote another admin first",
                )
        except HTTPException:
            raise
        except Exception:
            logger.exception("admin: delete_user last-owner check failed for %s", user_id)

    try:
        result = (
            sb.table("users")
            .update({"is_active": False})
            .eq("id", user_id)
            .eq("workspace_id", DEFAULT_WORKSPACE_ID)
            .execute()
        )
    except Exception:
        logger.exception("admin: delete_user failed for %s", user_id)
        raise HTTPException(status_code=500, detail="Failed to deactivate user")

    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

class CreateChannelBody(BaseModel):
    name: str
    team_id: Optional[str] = None
    source_type: Optional[str] = None
    sensitivity: Optional[str] = None


class PatchChannelBody(BaseModel):
    name: Optional[str] = None
    sensitivity: Optional[str] = None


@router.get("/channels")
async def list_channels(user=Depends(require_role("admin"))) -> dict:
    """List all channels in the default workspace."""
    try:
        result = (
            _client()
            .table("channels")
            .select("id, name, team_id, source_type, sensitivity, workspace_id")
            .eq("workspace_id", DEFAULT_WORKSPACE_ID)
            .order("name")
            .execute()
        )
        return {"channels": result.data}
    except Exception:
        logger.exception("admin: list_channels failed")
        raise HTTPException(status_code=500, detail="Failed to fetch channels")


@router.post("/channels", status_code=201)
async def create_channel(body: CreateChannelBody, user=Depends(require_role("admin"))) -> dict:
    """Create a new channel in the default workspace."""
    payload: dict = {
        "workspace_id": DEFAULT_WORKSPACE_ID,
        "name":         body.name,
    }
    if body.team_id:
        payload["team_id"] = body.team_id
    if body.source_type:
        payload["source_type"] = body.source_type
    if body.sensitivity:
        payload["sensitivity"] = body.sensitivity

    try:
        result = _client().table("channels").insert(payload).execute()
        return {"ok": True, "channel": result.data[0] if result.data else None}
    except Exception:
        logger.exception("admin: create_channel failed for '%s'", body.name)
        raise HTTPException(status_code=500, detail="Failed to create channel")


@router.patch("/channels/{channel_id}")
async def patch_channel(
    channel_id: str,
    body: PatchChannelBody,
    user=Depends(require_role("admin")),
) -> dict:
    """Update name or sensitivity for a channel."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        result = (
            _client()
            .table("channels")
            .update(updates)
            .eq("id", channel_id)
            .eq("workspace_id", DEFAULT_WORKSPACE_ID)
            .execute()
        )
    except Exception:
        logger.exception("admin: patch_channel failed for %s", channel_id)
        raise HTTPException(status_code=500, detail="Failed to update channel")

    if not result.data:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"ok": True}


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: str, user=Depends(require_role("admin"))) -> dict:
    """Hard-delete a channel."""
    try:
        result = (
            _client()
            .table("channels")
            .delete()
            .eq("id", channel_id)
            .eq("workspace_id", DEFAULT_WORKSPACE_ID)
            .execute()
        )
    except Exception:
        logger.exception("admin: delete_channel failed for %s", channel_id)
        raise HTTPException(status_code=500, detail="Failed to delete channel")

    if not result.data:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Audit log — separate prefix, same router
# ---------------------------------------------------------------------------

audit_router = APIRouter(prefix="/api", tags=["admin-audit"])


@audit_router.get("/audit-log")
async def get_audit_log(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    action: str = Query(default=""),
    target_type: str = Query(default=""),
    user=Depends(require_role("admin")),
) -> dict:
    """Paginated audit log from rbac_audit_log."""
    offset = (page - 1) * limit
    try:
        q = (
            _client()
            .table("rbac_audit_log")
            .select("id, actor_id, action, target_type, target_id, metadata, created_at")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )
        if action:
            q = q.eq("action", action)
        if target_type:
            q = q.eq("target_type", target_type)

        result = q.execute()
        return {"logs": result.data, "page": page, "limit": limit}
    except Exception:
        logger.exception("admin: get_audit_log failed")
        raise HTTPException(status_code=500, detail="Failed to fetch audit log")
