"""Planner agent — analyses query, returns ExecutionPlan via Gemini Pro."""

from __future__ import annotations

import logging

from agent.agents._gemini import call_gemini_json
from agent.config import settings
from agent.models import AgentTask, ExecutionPlan, QueryInput
from agent.prompts import PLANNER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


async def run_planner(query_input: QueryInput) -> ExecutionPlan:
    logger.info("planner: generating execution plan for query=%r", query_input.query)

    data = await call_gemini_json(
        model_name=settings.planner_model,
        system_prompt=PLANNER_SYSTEM_PROMPT,
        user_message=f"Query: {query_input.query}",
    )

    tasks = [AgentTask(**t) for t in data["tasks"]]
    plan = ExecutionPlan(tasks=tasks, reasoning=data.get("reasoning", ""))
    logger.info(
        "planner: plan has %d tasks — %s",
        len(tasks),
        [t.agent for t in tasks],
    )
    return plan
