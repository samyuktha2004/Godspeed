import logging

from fastapi import FastAPI

from agent.api import router as agent_router
from ingestion.api import router as ingestion_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="Enterprise Knowledge Copilot",
    version="0.1.0",
)

app.include_router(agent_router)
app.include_router(ingestion_router)
