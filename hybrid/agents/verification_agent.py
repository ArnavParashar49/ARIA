"""Verification agent — validates results and suggests retry."""

from __future__ import annotations

from hybrid.agents.base import BaseAgent
from hybrid.types import AgentRole, AgentTask, ExecutionContext, ToolResult


class VerificationAgent(BaseAgent):
    role = AgentRole.VERIFICATION

    def can_handle(self, task: AgentTask) -> bool:
        return task.mode.value == "planned" or "verify" in task.context

    def run(self, task: AgentTask, ctx: ExecutionContext) -> ToolResult:
        results = task.step_results
        if not results:
            return ToolResult(ok=False, text="No step results to verify.", tool_name="verify")

        failed = [
            n for n, txt in results.items()
            if str(txt).lower().startswith(("failed", "error", "could not"))
        ]
        if failed:
            return ToolResult(
                ok=False,
                text=f"Steps {failed} may have failed. Consider retry.",
                tool_name="verify",
            )

        previews = [str(v)[:80] for v in list(results.values())[:3]]
        summary = " | ".join(previews)
        return ToolResult(ok=True, text=f"Verified {len(results)} step(s). {summary}", tool_name="verify")
