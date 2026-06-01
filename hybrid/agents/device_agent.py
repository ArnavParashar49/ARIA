"""Device agent — IoT / smart hardware (isolated; extend without touching core)."""

from __future__ import annotations

from hybrid.agents.base import BaseAgent
from hybrid.registry import ToolRegistry
from hybrid.types import AgentRole, AgentTask, ExecutionContext, ToolResult

_DEVICE_TOOLS = frozenset()  # Register IoT tools with agent="device" when added


class DeviceAgent(BaseAgent):
    role = AgentRole.DEVICE

    def __init__(self, registry: ToolRegistry | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.registry = registry or ToolRegistry.instance()

    def can_handle(self, task: AgentTask) -> bool:
        name = task.context.get("tool_name", "")
        tool = self.registry.lookup(name)
        if tool and tool.agent == "device":
            return True
        return name in _DEVICE_TOOLS

    def run(self, task: AgentTask, ctx: ExecutionContext) -> ToolResult:
        name = task.context["tool_name"]
        args = task.context.get("tool_args") or {}
        return self.registry.invoke(name, args, ctx)
