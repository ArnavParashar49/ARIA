"""Base agent — all specialized agents extend this."""

from __future__ import annotations

from abc import ABC, abstractmethod

from hybrid.task_bus import TaskBus, get_task_bus
from hybrid.types import AgentMessage, AgentRole, AgentTask, ExecutionContext, ToolResult


class BaseAgent(ABC):
    role: AgentRole = AgentRole.TOOL

    def __init__(self, bus: TaskBus | None = None) -> None:
        self.bus = bus or get_task_bus()

    def emit(self, topic: str, payload: dict, task_id: str = "") -> None:
        self.bus.emit(topic, payload, task_id=task_id, source=self.role)

    @abstractmethod
    def can_handle(self, task: AgentTask) -> bool:
        ...

    @abstractmethod
    def run(self, task: AgentTask, ctx: ExecutionContext) -> ToolResult:
        ...
