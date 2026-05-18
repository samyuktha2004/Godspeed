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

from src.auth.email import send_email
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
            "team_id":              "default",
            "team":                 {"id": "default", "name": "Engineering"},
            "is_new_hire":          False,
            "allowed_channel_ids":  [_DEFAULT_CHANNEL],
        },
    },
}


def _make_cookie_kwargs() -> dict:
    """Cookie attributes — secure=True when running behind HTTPS."""
    return {
        "httponly": True,
        "samesite": "lax",
        "max_age":  SESSION_TTL,
        "secure":   settings.cookie_secure,
    }


async def _redis() -> aioredis.Redis:
    return aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
    )


async def _get_session(session_id: str) -> dict | None:
    r = await _redis()
    try:
        raw = await r.get(f"gs:session:{session_id}")
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning("session_read_failed", extra={"error": str(exc)})
        return None
    finally:
        await r.aclose()


async def _set_session(session_id: str, payload: dict) -> bool:
    """Returns False if Redis is unavailable."""
    r = await _redis()
    try:
        await r.setex(f"gs:session:{session_id}", SESSION_TTL, json.dumps(payload))
        return True
    except Exception as exc:
        logger.error("session_write_failed", extra={"error": str(exc)})
        return False
    finally:
        await r.aclose()


async def _del_session(session_id: str) -> None:
    r = await _redis()
    try:
        await r.delete(f"gs:session:{session_id}")
    except Exception as exc:
        logger.warning("session_delete_failed", extra={"error": str(exc)})
    finally:
        await r.aclose()


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
                user_obj = {
                    "id":                  db_user["id"],
                    "email":               db_user["email"],
                    "name":                db_user["name"],
                    "role":                db_user["role"],
                    "team_id":             team_id,
                    "team":                {"id": team_id, "name": team_id.capitalize()},
                    "is_new_hire":         db_user.get("is_new_hire", False),
                    "allowed_channel_ids": channel_ids,
                }
                logger.info("auth_login_db", extra={"email": email, "role": db_user["role"]})
    except Exception:
        logger.warning("auth_db_unavailable — falling back to hardcoded credentials")

    # ── Fall back to hardcoded dev credentials ───────────────
    if user_obj is None:
        entry = _CREDENTIALS.get(email)
        if not entry or entry["password"] != body.password:
            logger.warning("auth_failed", extra={"email": email})
            raise HTTPException(status_code=401, detail="Invalid credentials")
        user_obj = entry["user"]
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
    try:
        await r.setex(f"gs:oauth:state:{state}", _OAUTH_STATE_TTL, "1")
    finally:
        await r.aclose()

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
    try:
        state_key = f"gs:oauth:state:{state}"
        valid = await r.get(state_key)
        if not valid:
            logger.warning("oauth_invalid_state — possible CSRF or expired flow")
            return RedirectResponse(_frontend_error, status_code=302)
        await r.delete(state_key)
    finally:
        await r.aclose()

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

        user_obj = {
            "id":                  db_user["id"],
            "email":               db_user["email"],
            "name":                db_user["name"],
            "role":                db_user["role"],
            "team_id":             team_id,
            "team":                {"id": team_id, "name": team_id.capitalize()},
            "is_new_hire":         db_user.get("is_new_hire", False),
            "allowed_channel_ids": channel_ids,
        }

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
_INVITE_ALLOWED_ROLES = {"admin", "org_admin"}


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


@router.post("/invite")
async def send_invite(
    body: InviteRequest,
    caller: dict = Depends(_require_invite_role),
) -> dict:
    """Send an email invitation link. Requires admin or org_admin role."""
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
    try:
        await r.setex(f"gs:invite:{token}", _INVITE_TTL, payload)
    finally:
        await r.aclose()

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
    try:
        raw = await r.get(f"gs:invite:{token}")
    finally:
        await r.aclose()

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
    try:
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

        user_obj = {
            "id":                  db_user["id"],
            "email":               db_user["email"],
            "name":                db_user["name"],
            "role":                db_user["role"],
            "team_id":             team_id,
            "team":                {"id": team_id, "name": team_id.capitalize()},
            "is_new_hire":         db_user.get("is_new_hire", True),
            "allowed_channel_ids": channel_ids,
        }

    finally:
        await r.aclose()

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
