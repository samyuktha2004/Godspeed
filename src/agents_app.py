from __future__ import annotations

import logging

from fastapi import FastAPI

from ingestion.storage.qdrant_store import ensure_collection_exists
from src.confluence_agent.router import router as confluence_router
from src.file_agent.router import router as file_router
from src.jira_agent.router import router as jira_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Godspeed Ingestion Agents",
    description="Webhook + sync endpoints for JIRA, Confluence, and File ingestion agents.",
    version="1.0.0",
)

app.include_router(jira_router)
app.include_router(confluence_router)
app.include_router(file_router)


@app.on_event("startup")
async def startup() -> None:
    ensure_collection_exists()
    logger.info("agents_app: Qdrant collection ready")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
