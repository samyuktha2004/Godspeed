"""Auth endpoints — session-cookie-based, credentials from .env or Supabase users table."""

from __future__ import annotations

import json
import secrets
from datetime import datetime
from urllib.parse import urlencode
from uuid import uuid4

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from src.auth.permissions import permissions_for_role
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_TTL = 8 * 3600  # 8 hours
COOKIE_NAME = "gs_session"

# ---------------------------------------------------------------------------
# Dev fallback credentials (used when Supabase is not configured or user not
# found in DB). Keys are always lowercased for case-insensitive lookup.
# allowed_channel_ids defaults to the seeded General channel.
# ---------------------------------------------------------------------------
_DEFAULT_CHANNEL = "00000000-0000-0000-0000-000000000002"

_CREDENTIALS: dict[str, dict] = {
    settings.demo_email.lower(): {
        "password": settings.demo_password,
        "user": {
            "id":                   "user-demo",
            "email":                settings.demo_email.lower(),
            "name":                 "Demo User",
            "role":                 "engineer",
            "team_id":              "default",
            "team":                 {"id": "default", "name": "Engineering"},
            "is_new_hire":          False,
            "allowed_channel_ids":  [_DEFAULT_CHANNEL],
        },
    },
    settings.admin_email.lower(): {
        "password": settings.admin_password,
        "user": {
            "id":                   "user-admin",
            "email":                settings.admin_email.lower(),
            "name":                 "Admin",
            "role":                 "admin",
            "is_owner":             True,
            "team_id":              "default",
            "team":                 {"id": "default", "name": "Engineering"},
            "is_new_hire":          False,
            "allowed_channel_ids":  [_DEFAULT_CHANNEL],
        },
    },
}


def _make_cookie_kwargs() -> dict:
    """Cookie attributes — SameSite=None+Secure when embedded in a cross-site iframe (e.g. HF Spaces)."""
    import os as _os
    # HuggingFace injects SPACE_ID into every Space container
    on_hf = bool(_os.environ.get("SPACE_ID") or _os.environ.get("SPACE_AUTHOR_NAME"))
    samesite = "none" if on_hf else settings.cookie_samesite
    secure   = True   if on_hf else settings.cookie_secure
    return {
        "httponly": True,
        "samesite": samesite,
        "max_age":  SESSION_TTL,
        "secure":   secure,
    }


async def _redis() -> aioredis.Redis:
    # Delegates to the process-wide singleton — see src/utils/clients.py.
    # Do NOT call aclose() on the returned client; the lifespan hook owns it.
    from src.utils.clients import get_redis
    return await get_redis()


# In-memory fallback when Redis is unreachable (single-process deploy).
# Stored as (serialised_payload, expires_at_epoch) so we can enforce SESSION_TTL
# independently of Redis — otherwise a Redis outage during the session would
# effectively grant an infinite-lived cookie.
import time as _time
_mem_sessions: dict[str, tuple[str, float]] = {}


def _mem_expired(expires_at: float) -> bool:
    return _time.time() >= expires_at


async def _get_session(session_id: str) -> dict | None:
    try:
        r = await _redis()
        raw = await r.get(f"gs:session:{session_id}")
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    # Fallback to in-memory
    entry = _mem_sessions.get(session_id)
    if not entry:
        return None
    raw, expires_at = entry
    if _mem_expired(expires_at):
        _mem_sessions.pop(session_id, None)
        return None
    return json.loads(raw)


async def _set_session(session_id: str, payload: dict) -> bool:
    serialised = json.dumps(payload)
    try:
        r = await _redis()
        await r.setex(f"gs:session:{session_id}", SESSION_TTL, serialised)
        return True
    except Exception as exc:
        logger.warning("redis_unavailable — using in-memory session store", extra={"error": str(exc)})
        _mem_sessions[session_id] = (serialised, _time.time() + SESSION_TTL)
        return True


async def _del_session(session_id: str) -> None:
    _mem_sessions.pop(session_id, None)
    try:
        r = await _redis()
        await r.delete(f"gs:session:{session_id}")
    except Exception:
        pass


def _session_user_obj(db_user: dict, channel_ids: list[str], team_id: str) -> dict:
    """Canonical session user payload — keep every login path (password, OAuth,
    invite, register) in sync, including RBAC permissions and DPDPA consent state."""
    return {
        "id":                  db_user["id"],
        "email":               db_user["email"],
        "name":                db_user["name"],
        "role":                db_user["role"],
        "is_owner":            db_user.get("is_owner", False),
        "team_id":             team_id,
        "team":                {"id": team_id, "name": team_id.capitalize()},
        "is_new_hire":         db_user.get("is_new_hire", False),
        "allowed_channel_ids": channel_ids,
        "permissions":         permissions_for_role(db_user["role"]),
        "consent_at":          db_user.get("dpdpa_consent_at"),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email:    str
    password: str


@router.post("/login")
async def login(body: LoginRequest, response: Response) -> dict:
    email = body.email.lower()
    user_obj: dict | None = None

    # ── Try DB-backed auth first ─────────────────────────────
    try:
        import asyncio
        import bcrypt
        from src.auth.db import get_allowed_channel_ids, get_user_by_email, get_user_team_id

        db_user = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, get_user_by_email, email),
            timeout=5,
        )
        if db_user and db_user.get("password_hash"):
            pw_match = bcrypt.checkpw(
                body.password.encode(),
                db_user["password_hash"].encode(),
            )
            if pw_match:
                channel_ids = get_allowed_channel_ids(db_user["id"], db_user["role"])
                team_id = get_user_team_id(db_user["id"]) or "default"
                user_obj = _session_user_obj(db_user, channel_ids, team_id)
                logger.info("auth_login_db", extra={"email": email, "role": db_user["role"]})
    except Exception:
        logger.warning("auth_db_unavailable — falling back to hardcoded credentials")

    # ── Fall back to hardcoded dev credentials ───────────────
    if user_obj is None:
        if not settings.allow_demo_auth:
            # Fail closed: do not leak whether the email exists in DB
            logger.warning("auth_failed_demo_disabled", extra={"email": email})
            raise HTTPException(status_code=401, detail="Invalid credentials")
        entry = _CREDENTIALS.get(email)
        if not entry or entry["password"] != body.password:
            logger.warning("auth_failed", extra={"email": email})
            raise HTTPException(status_code=401, detail="Invalid credentials")
        user_obj = {**entry["user"], "permissions": permissions_for_role(entry["user"].get("role", "engineer"))}
        logger.info("auth_login_dev", extra={"email": email})

    session_id = str(uuid4())
    stored = await _set_session(
        session_id,
        {"user": user_obj, "created_at": datetime.utcnow().isoformat()},
    )
    if not stored:
        raise HTTPException(status_code=503, detail="Session store unavailable — try again shortly")

    response.set_cookie(key=COOKIE_NAME, value=session_id, **_make_cookie_kwargs())
    return {"user": user_obj}


class RegisterRequest(BaseModel):
    company_name: str
    name:         str
    email:        str
    password:     str


@router.post("/register")
async def register(body: RegisterRequest, response: Response) -> dict:
    """Bootstrap the first workspace owner (admin + is_owner).

    Single-workspace deploy: this creates the founding admin/owner in the default
    workspace and names the workspace after the company. Once an owner exists,
    further self-registration is rejected — additional users join via invite.
    """
    from src.auth.db import _DEFAULT_WORKSPACE_ID, get_allowed_channel_ids, get_user_by_email, record_audit

    email = body.email.lower().strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if len(body.company_name.strip()) < 2 or len(body.name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Company name and your name are required")

    try:
        from src.auth.db import _client as _db_client
        sb = _db_client()
    except Exception:
        logger.exception("register: Supabase unavailable")
        raise HTTPException(status_code=503, detail="Registration is temporarily unavailable")

    # Guard: a workspace may bootstrap only one founding owner via self-registration.
    try:
        owner_check = (
            sb.table("users")
            .select("id", count="exact")
            .eq("workspace_id", _DEFAULT_WORKSPACE_ID)
            .eq("is_owner", True)
            .eq("is_active", True)
            .execute()
        )
    except Exception:
        logger.exception("register: owner-existence check failed")
        raise HTTPException(status_code=503, detail="Registration is temporarily unavailable")
    if (owner_check.count or 0) >= 1:
        raise HTTPException(
            status_code=409,
            detail="Workspace already initialized — sign in or request an invite.",
        )

    if get_user_by_email(email):
        raise HTTPException(status_code=409, detail=f"User {email} already exists")

    import bcrypt
    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()

    try:
        insert_result = (
            sb.table("users")
            .insert({
                "workspace_id":  _DEFAULT_WORKSPACE_ID,
                "email":         email,
                "name":          body.name.strip(),
                "password_hash": password_hash,
                "role":          "admin",
                "is_owner":      True,
                "is_new_hire":   False,
                "is_active":     True,
            })
            .execute()
        )
        db_user = insert_result.data[0] if insert_result.data else None
        if not db_user:
            raise RuntimeError("insert returned no data")
    except Exception:
        logger.exception("register: owner insert failed for %s", email)
        raise HTTPException(status_code=500, detail="Failed to create workspace owner")

    # Name the workspace after the company, and place the owner on the default team.
    try:
        sb.table("workspaces").update({"name": body.company_name.strip()}).eq("id", _DEFAULT_WORKSPACE_ID).execute()
    except Exception:
        logger.warning("register: could not set workspace name for %s", email)
    try:
        sb.table("user_teams").insert({"user_id": db_user["id"], "team_id": "default"}).execute()
    except Exception:
        logger.warning("register: could not add owner to default team for %s", email)

    channel_ids = get_allowed_channel_ids(db_user["id"], db_user["role"])
    user_obj = _session_user_obj(db_user, channel_ids, "default")

    session_id = str(uuid4())
    stored = await _set_session(
        session_id,
        {"user": user_obj, "created_at": datetime.utcnow().isoformat()},
    )
    if not stored:
        raise HTTPException(status_code=503, detail="Session store unavailable — try again shortly")

    response.set_cookie(key=COOKIE_NAME, value=session_id, **_make_cookie_kwargs())
    record_audit(actor_id=db_user["id"], action="workspace_register", target_type="user", target_id=db_user["id"])
    logger.info("register_success email=%s company=%s", email, body.company_name.strip())
    return {"user": user_obj}


@router.post("/logout")
async def logout(response: Response, gs_session: str | None = Cookie(default=None)) -> dict:
    if gs_session:
        await _del_session(gs_session)
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.post("/refresh")
async def refresh(response: Response, gs_session: str | None = Cookie(default=None)) -> dict:
    if not gs_session:
        raise HTTPException(status_code=401, detail="No session")

    session = await _get_session(gs_session)
    if not session:
        response.delete_cookie(COOKIE_NAME)
        raise HTTPException(status_code=401, detail="Session expired")

    # Extend TTL — fire-and-forget; if Redis is down we still return the user
    await _set_session(gs_session, session)
    response.set_cookie(key=COOKIE_NAME, value=gs_session, **_make_cookie_kwargs())
    return {"user": session["user"]}


# ---------------------------------------------------------------------------
# Google OAuth2 / SSO
# ---------------------------------------------------------------------------

_GOOGLE_AUTH_URL    = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL   = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_OAUTH_STATE_TTL    = 600  # 10 minutes — window for completing the Google flow


@router.get("/google/authorize")
async def google_authorize() -> RedirectResponse:
    """Initiate Google OAuth2 Authorization Code Flow.

    Generates a CSRF state token, stores it in Redis for 10 min, then
    redirects the browser to Google's consent screen.
    """
    if not settings.google_oauth_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth is not configured on this server")

    state = secrets.token_urlsafe(32)
    r = await _redis()
    await r.setex(f"gs:oauth:state:{state}", _OAUTH_STATE_TTL, "1")

    params = {
        "client_id":     settings.google_oauth_client_id,
        "redirect_uri":  settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "offline",
        "prompt":        "select_account",
    }
    url = f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"
    logger.info("oauth_flow_started")
    return RedirectResponse(url, status_code=302)


@router.get("/google/callback")
async def google_callback(
    response: Response,
    code:  str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    """Handle Google's redirect after user approves (or denies) consent.

    Validates CSRF state, exchanges the authorization code for tokens,
    fetches the user's Google profile, upserts the Supabase user, creates
    a gs_session cookie, and redirects back to the frontend callback page.
    """
    _frontend_error = f"{settings.frontend_url}/auth/callback?error=oauth_failed"

    # Google denied or user cancelled
    if error or not code or not state:
        logger.warning("oauth_callback_rejected", extra={"google_error": error})
        return RedirectResponse(_frontend_error, status_code=302)

    # Validate CSRF state from Redis
    r = await _redis()
    state_key = f"gs:oauth:state:{state}"
    valid = await r.get(state_key)
    if not valid:
        logger.warning("oauth_invalid_state — possible CSRF or expired flow")
        return RedirectResponse(_frontend_error, status_code=302)
    await r.delete(state_key)

    # Exchange authorization code for Google tokens
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(_GOOGLE_TOKEN_URL, data={
                "grant_type":    "authorization_code",
                "code":          code,
                "client_id":     settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri":  settings.google_oauth_redirect_uri,
            })
            token_resp.raise_for_status()
            tokens = token_resp.json()

            userinfo_resp = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            userinfo_resp.raise_for_status()
            profile = userinfo_resp.json()

    except Exception:
        logger.exception("oauth_token_exchange_failed")
        return RedirectResponse(_frontend_error, status_code=302)

    # Require a verified email — unverified Google accounts are not allowed
    if not profile.get("email_verified"):
        logger.warning("oauth_unverified_email", extra={"email": profile.get("email")})
        return RedirectResponse(_frontend_error, status_code=302)

    # Upsert user in Supabase and resolve RBAC
    try:
        from src.auth.db import (
            get_allowed_channel_ids,
            get_or_create_oauth_user,
            get_user_team_id,
        )

        db_user = get_or_create_oauth_user(
            email=profile["email"],
            name=profile.get("name") or profile["email"].split("@")[0],
            oauth_sub=profile["sub"],
        )
        if not db_user:
            raise RuntimeError("get_or_create_oauth_user returned None")

        channel_ids = get_allowed_channel_ids(db_user["id"], db_user["role"])
        team_id     = get_user_team_id(db_user["id"]) or "default"

        user_obj = _session_user_obj(db_user, channel_ids, team_id)

    except Exception:
        logger.exception("oauth_user_upsert_failed", extra={"email": profile.get("email")})
        return RedirectResponse(_frontend_error, status_code=302)

    # Create session — same format as password login
    session_id = str(uuid4())
    stored = await _set_session(
        session_id,
        {"user": user_obj, "created_at": datetime.utcnow().isoformat()},
    )
    if not stored:
        logger.error("oauth_session_store_failed", extra={"email": user_obj["email"]})
        return RedirectResponse(_frontend_error, status_code=302)

    logger.info("oauth_login_success", extra={"email": user_obj["email"], "role": user_obj["role"]})

    redirect_resp = RedirectResponse(
        f"{settings.frontend_url}/auth/callback?oauth=success",
        status_code=302,
    )
    redirect_resp.set_cookie(key=COOKIE_NAME, value=session_id, **_make_cookie_kwargs())
    return redirect_resp


# ---------------------------------------------------------------------------
# Email invite flow
# ---------------------------------------------------------------------------

_INVITE_TTL = 7 * 24 * 3600  # 7 days in seconds
_DEFAULT_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"

# Allowed roles that can send invitations
_INVITE_ALLOWED_ROLES = {"admin", "manager"}


async def _require_invite_role(gs_session: str | None = Cookie(default=None)) -> dict:
    """Inline role guard (avoids circular import with deps.py)."""
    if not gs_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await _get_session(gs_session)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")
    user = session["user"]
    if user.get("role") not in _INVITE_ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{user.get('role')}' cannot send invitations",
        )
    return user


class InviteRequest(BaseModel):
    email: str
    name:  str
    role:  str = "engineer"


class AcceptInviteRequest(BaseModel):
    token:    str
    password: str


_VALID_INVITE_ROLES = {"engineer", "manager", "admin"}


@router.post("/invite")
async def send_invite(
    body: InviteRequest,
    caller: dict = Depends(_require_invite_role),
) -> dict:
    """Send an email invitation link. Requires admin role."""
    if body.role not in _VALID_INVITE_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{body.role}'. Allowed: {sorted(_VALID_INVITE_ROLES)}",
        )
    if caller.get("role") == "manager" and body.role != "engineer":
        raise HTTPException(
            status_code=403,
            detail="Managers can only invite engineers",
        )
    email = body.email.lower()

    # Check the user doesn't already exist
    try:
        from src.auth.db import get_user_by_email
        existing = get_user_by_email(email)
        if existing:
            raise HTTPException(status_code=409, detail=f"User {email} already exists")
    except HTTPException:
        raise
    except Exception:
        logger.warning("invite: could not check existing user for %s — proceeding", email)

    token = secrets.token_urlsafe(32)
    payload = json.dumps({
        "email":       email,
        "name":        body.name,
        "role":        body.role,
        "invited_by":  caller["id"],
    })

    r = await _redis()
    await r.setex(f"gs:invite:{token}", _INVITE_TTL, payload)

    invite_url = f"{settings.frontend_url}/accept-invite?token={token}"
    html = (
        f"<p>Hi {body.name},</p>"
        f"<p>You've been invited to join <strong>GodSpeed</strong>.</p>"
        f"<p><a href=\"{invite_url}\">Accept your invitation</a></p>"
        f"<p>This link expires in 7 days.</p>"
    )
    from src.auth.email import send_email_sync
    email_sent = send_email_sync(to=email, subject="You're invited to GodSpeed", html=html)

    logger.info("invite_sent to=%s by=%s role=%s email_sent=%s", email, caller["id"], body.role, email_sent)
    return {"ok": True, "email": email, "invite_url": invite_url, "email_sent": email_sent}


@router.get("/invite/{token}")
async def get_invite(token: str) -> dict:
    """Look up an invite token and return the display fields (no auth required)."""
    r = await _redis()
    raw = await r.get(f"gs:invite:{token}")

    if not raw:
        raise HTTPException(status_code=404, detail="Invite not found or expired")

    data = json.loads(raw)
    return {
        "email": data["email"],
        "name":  data["name"],
        "role":  data["role"],
    }


@router.post("/accept-invite")
async def accept_invite(body: AcceptInviteRequest, response: Response) -> dict:
    """Accept an invite, create the user account, and start a session."""
    r = await _redis()
    raw = await r.get(f"gs:invite:{body.token}")
    if not raw:
        raise HTTPException(status_code=404, detail="Invite not found or expired")
    invite = json.loads(raw)

    import bcrypt
    from src.auth.db import get_allowed_channel_ids, get_user_team_id

    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()

    # Insert user into Supabase
    try:
        from src.auth.db import _client as _db_client
        insert_result = (
            _db_client()
            .table("users")
            .insert({
                "workspace_id":  _DEFAULT_WORKSPACE_ID,
                "email":         invite["email"],
                "name":          invite["name"],
                "password_hash": password_hash,
                "role":          invite["role"],
                "is_new_hire":   True,
                "is_active":     True,
            })
            .execute()
        )
        db_user = insert_result.data[0] if insert_result.data else None
        if not db_user:
            raise RuntimeError("insert returned no data")
    except Exception:
        logger.exception("accept_invite: user insert failed for %s", invite["email"])
        raise HTTPException(status_code=500, detail="Failed to create user account")

    # One-time use — delete the invite key only after successful insert
    await r.delete(f"gs:invite:{body.token}")

    channel_ids = get_allowed_channel_ids(db_user["id"], db_user["role"])
    team_id     = get_user_team_id(db_user["id"]) or "default"

    user_obj = _session_user_obj(db_user, channel_ids, team_id)

    session_id = str(uuid4())
    stored = await _set_session(
        session_id,
        {"user": user_obj, "created_at": datetime.utcnow().isoformat()},
    )
    if not stored:
        raise HTTPException(status_code=503, detail="Session store unavailable — try again shortly")

    response.set_cookie(key=COOKIE_NAME, value=session_id, **_make_cookie_kwargs())
    logger.info("accept_invite_success email=%s role=%s", user_obj["email"], user_obj["role"])
    return {"user": user_obj}


# ---------------------------------------------------------------------------
# Profile + Password management
# ---------------------------------------------------------------------------

class UpdateProfileBody(BaseModel):
    name: str


class ChangePasswordBody(BaseModel):
    old_password: str
    new_password: str


@router.patch("/profile")
async def update_profile(
    body: UpdateProfileBody,
    response: Response,
    gs_session: str | None = Cookie(default=None),
) -> dict:
    """Update the authenticated user's display name and refresh the session."""
    if not gs_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await _get_session(gs_session)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")

    user = session["user"]
    try:
        from src.auth.db import _client as _db_client
        _db_client().table("users").update({"name": body.name}).eq("id", user["id"]).execute()
    except Exception:
        logger.exception("auth: update_profile failed for %s", user.get("id"))
        raise HTTPException(status_code=500, detail="Failed to update profile")

    # Refresh session with updated name
    user["name"] = body.name
    session["user"] = user
    await _set_session(gs_session, session)
    response.set_cookie(key=COOKIE_NAME, value=gs_session, **_make_cookie_kwargs())
    return {"ok": True, "user": user}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordBody,
    gs_session: str | None = Cookie(default=None),
) -> dict:
    """Verify the old bcrypt password and set a new one."""
    if not gs_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await _get_session(gs_session)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")

    user = session["user"]
    try:
        import bcrypt
        from src.auth.db import _client as _db_client

        result = (
            _db_client()
            .table("users")
            .select("password_hash")
            .eq("id", user["id"])
            .limit(1)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")

        current_hash = result.data[0].get("password_hash")
        if not current_hash:
            raise HTTPException(status_code=400, detail="No password set — use SSO login")

        if not bcrypt.checkpw(body.old_password.encode(), current_hash.encode()):
            raise HTTPException(status_code=401, detail="Old password is incorrect")

        new_hash = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()
        _db_client().table("users").update({"password_hash": new_hash}).eq("id", user["id"]).execute()

    except HTTPException:
        raise
    except Exception:
        logger.exception("auth: change_password failed for %s", user.get("id"))
        raise HTTPException(status_code=500, detail="Failed to change password")

    return {"ok": True}


# ---------------------------------------------------------------------------
# DPDPA — consent capture and data-subject rights (access / erasure)
# ---------------------------------------------------------------------------

_DEFAULT_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"


async def _require_session_user(gs_session: str | None) -> dict:
    """Resolve the authenticated user from the session cookie (no Depends — avoids
    the deps.py ↔ router.py circular import used by the rest of this module)."""
    if not gs_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await _get_session(gs_session)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")
    return session["user"]


@router.post("/me/consent")
async def record_consent(
    response: Response,
    gs_session: str | None = Cookie(default=None),
) -> dict:
    """Record the user's DPDPA consent acknowledgement and refresh the session."""
    user = await _require_session_user(gs_session)
    now_iso = datetime.utcnow().isoformat()
    try:
        from src.auth.db import _client as _db_client
        _db_client().table("users").update({"dpdpa_consent_at": now_iso}).eq("id", user["id"]).execute()
    except Exception:
        logger.exception("consent: failed to persist for %s", user.get("id"))
        raise HTTPException(status_code=500, detail="Failed to record consent")

    user["consent_at"] = now_iso
    session = await _get_session(gs_session) or {}
    session["user"] = user
    await _set_session(gs_session, session)
    response.set_cookie(key=COOKIE_NAME, value=gs_session, **_make_cookie_kwargs())
    return {"user": user}


@router.post("/me/data-export")
async def request_data_export(gs_session: str | None = Cookie(default=None)) -> dict:
    """DPDPA §11 Right to Access — gather the caller's personal data and email it."""
    user = await _require_session_user(gs_session)
    from src.auth.db import get_user_by_email, record_audit

    profile = get_user_by_email(user["email"]) or {k: user.get(k) for k in ("id", "email", "name", "role")}
    profile.pop("password_hash", None)

    # Gather the caller's own query history + feedback from Redis (bounded slice).
    history: list[dict] = []
    feedback: list[dict] = []
    try:
        r = await _redis()
        raw_list = await r.lrange("gs:queries", 0, 9999)
        for raw in raw_list:
            try:
                ev = json.loads(raw)
            except Exception:
                continue
            if ev.get("user_id") == user["id"]:
                history.append(ev)
                qid = ev.get("id")
                if qid:
                    fb = await r.get(f"gs:feedback:{qid}")
                    if fb:
                        try:
                            feedback.append({"query_id": qid, **json.loads(fb)})
                        except Exception:
                            pass
    except Exception:
        logger.warning("data_export: history gather failed for %s", user["id"])

    export = {
        "exported_at": datetime.utcnow().isoformat(),
        "profile":     profile,
        "query_history": history,
        "feedback":      feedback,
    }
    payload = json.dumps(export, indent=2, default=str)

    from src.auth.email import send_email_sync
    html = (
        f"<p>Hi {user.get('name', '')},</p>"
        f"<p>As requested, here is a copy of the personal data Godspeed holds about you "
        f"(DPDPA §11 Right to Access).</p>"
        f"<pre style=\"white-space:pre-wrap;font-size:12px\">{payload}</pre>"
    )
    email_sent = send_email_sync(to=user["email"], subject="Your Godspeed data export", html=html)

    record_audit(
        actor_id=user["id"], action="data_export", target_type="user", target_id=user["id"],
        metadata={"records": len(history), "email_sent": email_sent},
    )
    logger.info("data_export email=%s records=%d email_sent=%s", user["email"], len(history), email_sent)
    return {"ok": True, "email_sent": email_sent}


@router.post("/me/delete-request")
async def request_account_deletion(
    response: Response,
    gs_session: str | None = Cookie(default=None),
) -> dict:
    """DPDPA §12 Right to Erasure — soft-delete the caller and notify workspace admins."""
    user = await _require_session_user(gs_session)
    from src.auth.db import record_audit

    try:
        from src.auth.db import _client as _db_client
        sb = _db_client()
    except Exception:
        logger.exception("delete_request: Supabase unavailable")
        raise HTTPException(status_code=503, detail="Deletion is temporarily unavailable")

    # Last-owner guard — an owner must transfer ownership before erasing their account.
    if user.get("is_owner"):
        try:
            owner_count = (
                sb.table("users")
                .select("id", count="exact")
                .eq("workspace_id", _DEFAULT_WORKSPACE_ID)
                .eq("is_owner", True)
                .eq("is_active", True)
                .execute()
            )
        except Exception:
            logger.exception("delete_request: owner-count check failed")
            raise HTTPException(status_code=503, detail="Could not verify owner count — try again")
        if (owner_count.count or 0) <= 1:
            raise HTTPException(
                status_code=409,
                detail="Transfer ownership to another admin before deleting your account.",
            )

    # Soft-delete: revoke access immediately; retention purge happens later.
    try:
        sb.table("users").update({"is_active": False}).eq("id", user["id"]).execute()
    except Exception:
        logger.exception("delete_request: soft-delete failed for %s", user["id"])
        raise HTTPException(status_code=500, detail="Failed to process deletion request")

    # Notify active workspace admins/owners.
    try:
        admins = (
            sb.table("users")
            .select("email, name")
            .eq("workspace_id", _DEFAULT_WORKSPACE_ID)
            .eq("role", "admin")
            .eq("is_active", True)
            .execute()
        )
        from src.auth.email import send_email_sync
        html = (
            f"<p>{user.get('name', '')} ({user['email']}) has requested erasure of their account "
            f"under DPDPA §12.</p>"
            f"<p>Their access has been revoked. Please complete any required data purge within the "
            f"retention window.</p>"
        )
        for admin in (admins.data or []):
            if admin.get("email") and admin["email"] != user["email"]:
                send_email_sync(to=admin["email"], subject="Account deletion request", html=html)
    except Exception:
        logger.warning("delete_request: admin notification failed for %s", user["email"])

    record_audit(
        actor_id=user["id"], action="delete_request", target_type="user", target_id=user["id"],
    )

    # Invalidate the caller's session and clear the cookie.
    if gs_session:
        await _del_session(gs_session)
    response.delete_cookie(COOKIE_NAME)
    logger.info("delete_request email=%s", user["email"])
    return {"ok": True}
