"""Planner agent — analyses query, returns ExecutionPlan via Gemini Pro."""

from __future__ import annotations

import logging

from agent.agents._gemini import call_gemini_json
from agent.config import settings
from agent.models import AgentTask, ExecutionPlan, QueryInput, RoutingDecision
from agent.prompts import PLANNER_SYSTEM_PROMPT
from typing import Optional

logger = logging.getLogger(__name__)


async def run_planner(
    query_input: QueryInput,
    routing_decision: Optional[RoutingDecision] = None,
    manifest_summary: str = "",
) -> ExecutionPlan:
    logger.info("planner: generating execution plan for query=%r", query_input.query)

    routing_context = ""
    if routing_decision is not None:
        routing_context = (
            "\n\nRouter suggestion (deterministic pre-pass — prefer these, add others "
            "only if the query clearly needs them):\n"
            f"- suggested_agents: {routing_decision.suggested_agents}\n"
            f"- confidence: {routing_decision.confidence}\n"
            f"- reasoning: {routing_decision.reasoning}"
        )
    manifest_context = (
        f"\n\nKnown knowledge sources for this team:\n{manifest_summary}"
        if manifest_summary
        else ""
    )

    data = await call_gemini_json(
        model_name=settings.planner_model,
        system_prompt=PLANNER_SYSTEM_PROMPT,
        user_message=f"Query: {query_input.query}{routing_context}{manifest_context}",
    )

    tasks = [AgentTask(**t) for t in data["tasks"]]
    plan = ExecutionPlan(tasks=tasks, reasoning=data.get("reasoning", ""))
    logger.info(
        "planner: plan has %d tasks — %s",
        len(tasks),
        [t.agent for t in tasks],
    )
    return plan
