"""Auth endpoints — session-cookie-based, credentials from .env or Supabase users table."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

import redis.asyncio as aioredis
from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel

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
    return aioredis.from_url(settings.redis_url, decode_responses=True)


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
        import bcrypt
        from src.auth.db import get_allowed_channel_ids, get_user_by_email, get_user_team_id

        db_user = get_user_by_email(email)
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
