"""Memory agent — preferences and long-term facts."""

from __future__ import annotations

from hybrid.agents.base import BaseAgent
from hybrid.registry import ToolRegistry
from hybrid.types import AgentRole, AgentTask, ExecutionContext, ToolResult


class MemoryAgent(BaseAgent):
    role = AgentRole.MEMORY

    def __init__(self, registry: ToolRegistry | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.registry = registry or ToolRegistry.instance()

    def can_handle(self, task: AgentTask) -> bool:
        return task.context.get("tool_name") in ("save_memory", "contact_manager")

    def run(self, task: AgentTask, ctx: ExecutionContext) -> ToolResult:
        name = task.context["tool_name"]
        args = task.context.get("tool_args") or {}
        return self.registry.invoke(name, args, ctx)
