"""Adaptive routing — fast path (no planner) vs planned execution. No extra LLM calls.

Fast-path rules are now DECLARATIVE — they live on the registered tools in the
registry (see RegisteredTool.fast_path_patterns), not hardcoded here.
"""

from __future__ import annotations

import re

from hybrid.registry import ToolRegistry
from hybrid.types import AgentTask, ExecutionMode, RouteDecision


# Multi-step / reasoning cues → planned path
_COMPLEX_RE = re.compile(
    r"\b("
    r"and then|after that|then email|email (?:it |them )?to|schedule|notify|"
    r"research .+ and|summarize .+ and|compare .+ and|create a (?:report|table|summary)|"
    r"find .+ (?:nearby|near me).+ and|multiple steps|step by step|"
    r"and also|and open|also open|also play|also send"
    r")\b",
    re.I,
)

_AGENT_TASK_RE = re.compile(
    r"\b(create|develop|scaffold|multi.?step task)\b",
    re.I,
)


class AdaptiveRouter:
    """Classifies requests without calling an LLM.

    Fast-path rules are read from the tool registry — to add a new fast-path
    tool, set `fast_path_patterns` on the RegisteredTool, not a regex here.
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or ToolRegistry.instance()

    def route(self, user_text: str, *, tool_hint: str | None = None) -> RouteDecision:
        text = (user_text or "").strip()
        if not text:
            return RouteDecision(mode=ExecutionMode.DIRECT, reason="empty")

        if tool_hint and self.registry.lookup(tool_hint):
            return RouteDecision(
                mode=ExecutionMode.DIRECT,
                tool_name=tool_hint,
                reason="explicit_tool_hint",
            )

        if self._is_complex(text):
            task = AgentTask.new(text, ExecutionMode.PLANNED, user_text=text)
            return RouteDecision(
                mode=ExecutionMode.PLANNED,
                reason="complex_goal",
                agent_task=task,
            )

        fast = self._match_fast_path(text)
        if fast:
            return fast

        return RouteDecision(mode=ExecutionMode.DIRECT, reason="defer_to_live_model")

    def _is_complex(self, text: str) -> bool:
        if _AGENT_TASK_RE.search(text):
            return True
        if text.count(" and ") >= 2 and len(text.split()) >= 8:
            return True
        return bool(_COMPLEX_RE.search(text))

    def _match_fast_path(self, text: str) -> RouteDecision | None:
        normalized = re.sub(r"\s+", " ", text).strip()
        for tool in self.registry._tools.values():
            if not tool.fast_eligible:
                continue
            if not tool.fast_path_patterns:
                continue
            for pattern_str, arg_map in tool.fast_path_patterns:
                pattern = re.compile(pattern_str, re.I)
                m = pattern.search(normalized)
                if not m:
                    continue
                # Build args from the pattern match groups
                args = {}
                for arg_key, group_key in arg_map.items():
                    try:
                        args[arg_key] = m.group(int(group_key))
                    except (ValueError, IndexError):
                        args[arg_key] = group_key  # literal value
                return RouteDecision(
                    mode=ExecutionMode.DIRECT,
                    tool_name=tool.name,
                    tool_args=args,
                    reason="fast_path_regex",
                    confidence=0.92,
                )
        return None
