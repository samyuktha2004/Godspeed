from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.api import router as agent_router
from graph_store.api import router as graph_router
from graph_store.stream import router as graph_stream_router
from ingestion.api import router as ingestion_router
from src.confluence_agent.router import router as confluence_router
from toolsforgitnotionslack.router import router as tools_router
from src.file_agent.router import router as file_router
from src.jira_agent.router import router as jira_router
from src.utils.middleware import RequestLoggingMiddleware
from src.auth.router import router as auth_router
from src.analytics.router import router as analytics_router
from src.admin.router import router as admin_router
from src.admin.users_api import router as admin_users_router
from src.admin.users_api import audit_router as admin_audit_router
from src.workspace.router import router as workspace_router
from src.ws.router import router as ws_router
# src.utils.logger configures the root JSON handler on import


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    from graph_store.writer import close_driver
    await close_driver()


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
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(analytics_router)
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
# Health endpoint — pinged by admin dashboard + Docker healthcheck
# ---------------------------------------------------------------------------

@app.get("/health", tags=["infra"])
async def health() -> dict:
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

    # Redis
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(_settings.redis_url, socket_connect_timeout=3)
        await r.ping()
        await r.aclose()
        results["redis"] = "ok"
    except Exception as exc:
        results["redis"] = f"error: {exc}"
        results["status"] = "degraded"

    # Qdrant — supports local (host+port) and hosted (url+api_key)
    try:
        from qdrant_client import AsyncQdrantClient
        if _settings.qdrant_url:
            qc = AsyncQdrantClient(
                url=_settings.qdrant_url,
                api_key=_settings.qdrant_api_key or None,
                timeout=3,
            )
        else:
            qc = AsyncQdrantClient(
                host=_settings.qdrant_host,
                port=_settings.qdrant_port,
                timeout=3,
            )
        await qc.get_collections()
        await qc.close()
        results["qdrant"] = "ok"
    except Exception as exc:
        results["qdrant"] = f"error: {exc}"
        results["status"] = "degraded"

    return results
