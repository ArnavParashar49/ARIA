"""Planner agent — breaks complex goals into steps via LLM."""

from __future__ import annotations

import json
import re

from hybrid.agents.base import BaseAgent
from hybrid.types import AgentRole, AgentTask, ExecutionContext, ToolResult


_PLAN_PROMPT = """You are the planning module of NEO. Break the user's goal into steps.
Return ONLY valid JSON:
{
  "steps": [
    {"step": 1, "tool": "tool_name", "parameters": {...}, "depends_on": []},
    {"step": 2, "tool": "tool_name", "parameters": {...}, "depends_on": [1]}
  ]
}
Keep it minimal — max 5 steps. Prefer web_search for information gathering.
Never reference prior step results in parameters — steps are ordered, not parameter-chained."""


class PlannerAgent(BaseAgent):
    role = AgentRole.PLANNER

    def can_handle(self, task: AgentTask) -> bool:
        return task.mode.value == "planned"

    def run(self, task: AgentTask, ctx: ExecutionContext) -> ToolResult:
        from core.llm import ask_json

        self.emit("plan.start", {"goal": task.goal[:120]}, task_id=task.id)
        try:
            plan = ask_json(task.goal, system=_PLAN_PROMPT, temperature=0.2)
            steps = plan.get("steps") or []
            task.plan_steps = steps
            self.emit("plan.done", {"steps": len(steps)}, task_id=task.id)
            return ToolResult(
                ok=True,
                text=f"Plan with {len(steps)} steps.",
                data={"plan": plan},
                tool_name="planner",
            )
        except Exception as e:
            return ToolResult(ok=False, text=f"Planning failed: {e}", tool_name="planner")
