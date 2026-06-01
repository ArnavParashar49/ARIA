"""Research agent — web search and information gathering tools."""

from __future__ import annotations

from hybrid.agents.base import BaseAgent
from hybrid.registry import ToolRegistry
from hybrid.types import AgentRole, AgentTask, ExecutionContext, ToolResult

_RESEARCH_TOOLS = frozenset({
    "web_search",
    "youtube_video",
    "flight_finder",
    "screen_process",
    "screen_act",
})


class ResearchAgent(BaseAgent):
    role = AgentRole.RESEARCH

    def __init__(self, registry: ToolRegistry | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.registry = registry or ToolRegistry.instance()

    def can_handle(self, task: AgentTask) -> bool:
        return task.context.get("tool_name") in _RESEARCH_TOOLS

    def run(self, task: AgentTask, ctx: ExecutionContext) -> ToolResult:
        name = task.context["tool_name"]
        args = task.context.get("tool_args") or {}
        return self.registry.invoke(name, args, ctx)
