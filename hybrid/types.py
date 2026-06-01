"""Structured types for the hybrid agent layer."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class ExecutionMode(Enum):
    DIRECT = "direct"      # Fast path: one tool, no planner
    PLANNED = "planned"    # Planner + specialized agents


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class AgentRole(Enum):
    ORCHESTRATOR = "orchestrator"
    PLANNER = "planner"
    TOOL = "tool"
    MEMORY = "memory"
    RESEARCH = "research"
    SYSTEM = "system"
    DEVICE = "device"
    VERIFICATION = "verification"


@dataclass
class AgentMessage:
    """Message on the task bus — agents subscribe by role or topic."""

    topic: str
    payload: dict[str, Any] = field(default_factory=dict)
    task_id: str = ""
    source: AgentRole = AgentRole.ORCHESTRATOR
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentTask:
    """Unit of work passed between orchestrator and agents."""

    id: str
    goal: str
    mode: ExecutionMode
    user_text: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    plan_steps: list[dict[str, Any]] = field(default_factory=list)
    step_results: dict[int, str] = field(default_factory=dict)
    final_result: str = ""
    error: str = ""
    created_at: float = field(default_factory=time.time)

    @staticmethod
    def new(goal: str, mode: ExecutionMode, user_text: str = "", **ctx: Any) -> AgentTask:
        return AgentTask(
            id=str(uuid.uuid4())[:12],
            goal=goal,
            mode=mode,
            user_text=user_text or goal,
            context=dict(ctx),
        )


@dataclass
class RouteDecision:
    mode: ExecutionMode
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    reason: str = ""
    confidence: float = 1.0
    agent_task: AgentTask | None = None


@dataclass
class ToolResult:
    ok: bool
    text: str
    data: dict[str, Any] = field(default_factory=dict)
    tool_name: str = ""


@dataclass
class ExecutionContext:
    """Runtime context for tool handlers (UI, memory, session)."""

    ui: Any = None
    speak: Callable[..., Any] | None = None
    last_user_log: str = ""
    session_memory: Any = None
    extras: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.extras.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.extras[key] = value


ToolHandler = Callable[[dict[str, Any], ExecutionContext], str]
ToolGuard = Callable[[dict[str, Any], ExecutionContext], str | None]
