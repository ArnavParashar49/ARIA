"""Planner agent — breaks complex goals into steps (single LLM call via existing planner)."""

from __future__ import annotations

from hybrid.agents.base import BaseAgent
from hybrid.types import AgentRole, AgentTask, ExecutionContext, ToolResult


class PlannerAgent(BaseAgent):
    role = AgentRole.PLANNER

    def can_handle(self, task: AgentTask) -> bool:
        return task.mode.value == "planned"

    def run(self, task: AgentTask, ctx: ExecutionContext) -> ToolResult:
        from agent.planner import create_plan

        self.emit("plan.start", {"goal": task.goal[:120]}, task_id=task.id)
        try:
            plan = create_plan(task.goal)
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
