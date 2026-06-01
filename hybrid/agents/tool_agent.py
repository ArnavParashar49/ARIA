"""Tool execution agent — invokes ToolRegistry handlers."""

from __future__ import annotations

from hybrid.agents.base import BaseAgent
from hybrid.registry import ToolRegistry
from hybrid.types import AgentRole, AgentTask, ExecutionContext, ToolResult


class ToolExecutionAgent(BaseAgent):
    role = AgentRole.TOOL

    def __init__(self, registry: ToolRegistry | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.registry = registry or ToolRegistry.instance()

    def can_handle(self, task: AgentTask) -> bool:
        return bool(task.context.get("tool_name"))

    def run(self, task: AgentTask, ctx: ExecutionContext) -> ToolResult:
        name = task.context.get("tool_name", "")
        args = task.context.get("tool_args") or {}
        self.emit("tool.start", {"tool": name, "args": args}, task_id=task.id)
        result = self.registry.invoke(name, args, ctx)
        self.emit(
            "tool.done",
            {"tool": name, "ok": result.ok, "preview": result.text[:200]},
            task_id=task.id,
        )
        return result
