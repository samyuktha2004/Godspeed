import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI

from agent.api import router as agent_router
from graph_store.api import router as graph_router
from graph_store.stream import router as graph_stream_router
from ingestion.api import router as ingestion_router
from src.confluence_agent.router import router as confluence_router
from toolsforgitnotionslack.router import router as tools_router
from src.file_agent.router import router as file_router
from src.jira_agent.router import router as jira_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


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

app.include_router(agent_router)
app.include_router(ingestion_router)
app.include_router(graph_router)
app.include_router(graph_stream_router)
app.include_router(jira_router)
app.include_router(confluence_router)
app.include_router(file_router)
app.include_router(tools_router)
