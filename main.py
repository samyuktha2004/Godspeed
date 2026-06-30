from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from agent.api import router as agent_router
from graph_store.api import router as graph_router
from graph_store.stream import router as graph_stream_router
from ingestion.api import router as ingestion_router
from src.confluence_agent.router import router as confluence_router
from tools.router import router as tools_router
from src.file_agent.router import router as file_router
from src.jira_agent.router import router as jira_router
from src.utils.middleware import OriginCheckMiddleware, RequestLoggingMiddleware
from src.auth.router import router as auth_router
from src.analytics.router import router as analytics_router
from src.anomaly.router import router as anomaly_router
from src.admin.router import router as admin_router
from src.admin.users_api import router as admin_users_router
from src.admin.users_api import audit_router as admin_audit_router
from src.workspace.router import router as workspace_router
from src.ws.router import router as ws_router
from src.utils.logger import get_logger
# src.utils.logger configures the root JSON handler on import

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.utils.clients import close_clients, init_clients

    logger.info("app_startup_begin")
    await init_clients()
    logger.info("app_startup_ready")
    try:
        yield
    finally:
        from graph_store.writer import close_driver
        logger.info("app_shutdown_begin")
        await close_clients()
        await close_driver()
        logger.info("app_shutdown_done")


app = FastAPI(
    title="Enterprise Knowledge Copilot",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow the Vite dev server and any configured origins
# ---------------------------------------------------------------------------
from src.config import settings as _settings

_cors_origins = [o.strip() for o in _settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
# Origin-based CSRF defense: rejects state-changing cookie-bearing requests
# whose Origin/Referer is not in the CORS allow-list. Necessary when running
# behind SameSite=None (HF Spaces iframe).
app.add_middleware(OriginCheckMiddleware, allowed_origins=_cors_origins)
app.add_middleware(RequestLoggingMiddleware)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(analytics_router)
app.include_router(anomaly_router)
app.include_router(admin_router)
app.include_router(admin_users_router)
app.include_router(admin_audit_router)
app.include_router(workspace_router)
app.include_router(ws_router)
app.include_router(agent_router)
app.include_router(ingestion_router)
app.include_router(graph_router)
app.include_router(graph_stream_router)
app.include_router(jira_router)
app.include_router(confluence_router)
app.include_router(file_router)
app.include_router(tools_router)


# ---------------------------------------------------------------------------
# Health endpoint — must be registered BEFORE the SPA catch-all
# ---------------------------------------------------------------------------

@app.get("/health", tags=["infra"])
async def health(response: Response) -> dict:
    import asyncio

    results: dict = {"status": "ok", "neo4j": "unknown", "redis": "unknown", "qdrant": "unknown"}

    # Neo4j — reuse module-level singleton; do not close it here
    try:
        from graph_store.writer import get_driver
        driver = get_driver()
        await asyncio.wait_for(driver.verify_connectivity(), timeout=3)
        results["neo4j"] = "ok"
    except Exception as exc:
        results["neo4j"] = f"error: {exc}"
        results["status"] = "degraded"

    # Redis — reuse module-level singleton, probe with a short timeout
    try:
        from src.utils.clients import get_redis
        r = await get_redis()
        await asyncio.wait_for(r.ping(), timeout=3)
        results["redis"] = "ok"
    except Exception as exc:
        results["redis"] = f"error: {exc}"
        results["status"] = "degraded"

    # Qdrant — reuse module-level singleton, probe with a short timeout
    try:
        from src.utils.clients import get_qdrant
        qc = get_qdrant()
        await asyncio.wait_for(qc.get_collections(), timeout=3)
        results["qdrant"] = "ok"
    except Exception as exc:
        results["qdrant"] = f"error: {exc}"
        results["status"] = "degraded"

    if results["status"] != "ok":
        response.status_code = 503
        logger.warning("health_degraded", extra=results)
    else:
        logger.info("health_ok", extra=results)

    return results


# ---------------------------------------------------------------------------
# Serve React build — SPA catch-all MUST be last (catches everything else)
# ---------------------------------------------------------------------------
import os as _os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse as _FileResponse

_dist = _os.path.join(_os.path.dirname(__file__), "frontend", "dist")
if _os.path.exists(_dist):
    logger.info("spa_dist_mounted", extra={"dist": _dist})
    app.mount("/assets", StaticFiles(directory=_os.path.join(_dist, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file = _os.path.join(_dist, full_path)
        if _os.path.isfile(file):
            return _FileResponse(file)
        return _FileResponse(_os.path.join(_dist, "index.html"))
else:
    logger.warning("spa_dist_missing", extra={"dist": _dist})
