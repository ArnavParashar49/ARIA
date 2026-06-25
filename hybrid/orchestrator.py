"""Orchestrator — entry point for routing, execution, and agent collaboration."""

from __future__ import annotations

import asyncio
import os
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from hybrid.agents import (
    DeviceAgent,
    MemoryAgent,
    PlannerAgent,
    ResearchAgent,
    SystemAgent,
    ToolExecutionAgent,
    VerificationAgent,
)
from hybrid.registry import ToolRegistry
from hybrid.router import AdaptiveRouter
from hybrid.task_bus import TaskBus, get_task_bus
from hybrid.types import (
    AgentTask,
    ExecutionContext,
    ExecutionMode,
    RouteDecision,
    ToolResult,
)


class Orchestrator:
    """
    Lightweight coordinator:
    - DIRECT: one tool via registry (fast path or Gemini tool call)
    - PLANNED: planner → parallel steps where possible → verification
    """

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        bus: TaskBus | None = None,
    ) -> None:
        self.registry = registry or ToolRegistry.instance()
        self.bus = bus or get_task_bus()
        self.router = AdaptiveRouter(self.registry)
        self.planner = PlannerAgent(self.bus)
        self.tool_agent = ToolExecutionAgent(self.registry, bus=self.bus)
        self.memory_agent = MemoryAgent(self.registry, bus=self.bus)
        self.research_agent = ResearchAgent(self.registry, bus=self.bus)
        self.system_agent = SystemAgent(self.registry, bus=self.bus)
        self.device_agent = DeviceAgent(self.registry, bus=self.bus)
        self.verifier = VerificationAgent(bus=self.bus)
        self._agents = [
            self.memory_agent,
            self.research_agent,
            self.system_agent,
            self.device_agent,
            self.tool_agent,
        ]

    def build_context(self, neo: Any) -> ExecutionContext:
        return ExecutionContext(
            ui=getattr(neo, "ui", None),
            speak=getattr(neo, "notify_user", getattr(neo, "speak", None)),
            last_user_log=getattr(neo, "_last_user_log", ""),
            session_memory=None,
            extras={"neo": neo, "orchestrator": self},
        )

    def try_fast_path(self, user_text: str, ctx: ExecutionContext) -> ToolResult | None:
        """Regex routing — no planner, no extra LLM. Returns None if not matched."""
        decision = self.router.route(user_text)
        if decision.mode != ExecutionMode.DIRECT or not decision.tool_name:
            return None
        if decision.reason == "defer_to_live_model":
            return None
        task = AgentTask.new(
            user_text,
            ExecutionMode.DIRECT,
            user_text=user_text,
            tool_name=decision.tool_name,
            tool_args=decision.tool_args or {},
        )
        print(f"[Orchestrator] ⚡ Fast path → {decision.tool_name} ({decision.reason})")
        return self._dispatch_to_agent(task, ctx)

    def route_user_goal(self, user_text: str) -> RouteDecision:
        return self.router.route(user_text)

    def _pick_agent(self, tool_name: str):
        task = AgentTask.new("", ExecutionMode.DIRECT, tool_name=tool_name)
        for agent in self._agents:
            if agent.can_handle(task):
                return agent
        return self.tool_agent

    def _dispatch_to_agent(self, task: AgentTask, ctx: ExecutionContext) -> ToolResult:
        agent = self._pick_agent(task.context.get("tool_name", ""))
        return agent.run(task, ctx)

    def execute_tool_sync(
        self,
        name: str,
        args: dict,
        ctx: ExecutionContext,
        *,
        pre_hook: Any = None,
        post_hook: Any = None,
    ) -> ToolResult:
        """Synchronous tool execution (called from thread pool)."""
        if pre_hook:
            pre_hook(name, args, ctx)

        if name == "shutdown_neo":
            return self._handle_shutdown(ctx)

        task = AgentTask.new(
            args.get("text") or args.get("goal") or name,
            ExecutionMode.DIRECT,
            tool_name=name,
            tool_args=args,
        )
        result = self._dispatch_to_agent(task, ctx)

        if name == "save_memory":
            result.data["silent"] = True

        if name == "web_search" and result.ok:
            neo = ctx.get("neo")
            if neo is not None:
                neo._last_search_result = result.text
            try:
                from core.action_context import set_web_search

                set_web_search(
                    query=args.get("query", ""),
                    summary=result.text or "",
                )
            except Exception as e:
                print(f"[Orchestrator] action_context web_search: {e}")

        if name == "flight_finder" and result.ok:
            neo = ctx.get("neo")
            if neo is not None:
                neo._last_search_result = result.text

        if post_hook:
            post_hook(name, args, ctx, result)

        return result

    def _handle_shutdown(self, ctx: ExecutionContext) -> ToolResult:
        print("[NEO] Shutdown requested.")

        def _shutdown():
            time.sleep(0.4)
            os._exit(0)

        threading.Thread(target=_shutdown, daemon=True).start()
        return ToolResult(ok=True, text="Goodbye.", tool_name="shutdown_neo")

    def run_planned_sync(self, goal: str, ctx: ExecutionContext) -> str:
        """Planned path: GoalDispatcher for multi-task, then planner for complex single goals."""
        # First check if this is actually multiple independent goals
        from core.goal_dispatcher import get_dispatcher, split_goals
        goals = split_goals(goal)
        if len(goals) >= 2:
            print(f"[Orchestrator] GoalDispatcher: {len(goals)} independent goals, dispatching in parallel")
            result = get_dispatcher().dispatch(goal, ctx)
            return result.summary

        # Single complex goal -> planner + executor
        task = AgentTask.new(goal, ExecutionMode.PLANNED, user_text=goal)
        self.bus.emit("task.start", {"goal": goal, "mode": "planned"}, task_id=task.id)

        plan_result = self.planner.run(task, ctx)
        if not plan_result.ok:
            return plan_result.text

        from core.session_state import save_session, clear_session
        save_session({"goal": goal, "mode": "planned", "task_id": task.id})

        plan = plan_result.data.get("plan") or {}
        steps = plan.get("steps") or []
        if not steps:
            clear_session()
            return f"No steps generated for goal: '{goal}'."

        independent: list[dict] = []
        dependent: list[dict] = []
        for step in steps:
            deps = step.get("depends_on") or []
            if deps:
                dependent.append(step)
            else:
                independent.append(step)

        if ctx.speak and len(independent) > 0:
            ctx.speak(f"I've created a plan with {len(steps)} steps. Starting {len(independent)} tasks in parallel.", interrupt=False)

        def run_step(step: dict) -> tuple[int, str]:
            tool = step.get("tool", "")
            params = step.get("parameters") or {}
            sub = AgentTask.new(
                goal,
                ExecutionMode.DIRECT,
                tool_name=tool,
                tool_args=params,
            )
            res = self._dispatch_to_agent(sub, ctx)
            num = int(step.get("step", 0))
            if ctx.speak:
                ctx.speak(f"Step {num} completed.", interrupt=False)
            return num, res.text

        with ThreadPoolExecutor(max_workers=min(4, max(1, len(independent)))) as pool:
            futures = {pool.submit(run_step, s): s for s in independent}
            for fut in as_completed(futures):
                num, text = fut.result()
                task.step_results[num] = text

        for step in sorted(dependent, key=lambda s: int(s.get("step", 0))):
            num, text = run_step(step)
            task.step_results[num] = text

        verify = self.verifier.run(task, ctx)
        clear_session()
        if not verify.ok:
            return verify.text
        
        parts = [str(v) for v in task.step_results.values() if v]
        final = " ".join(parts)[:2000] if parts else plan_result.text
        task.final_result = final
        self.bus.emit("task.done", {"goal": goal, "ok": True}, task_id=task.id)
        return final

    async def execute_tool_for_live(
        self,
        fc: Any,
        neo: Any,
        *,
        on_finish: Any = None,
    ) -> Any:
        """Async wrapper used by NeoLive._execute_tool."""
        from google.genai import types

        name = fc.name
        args = dict(fc.args or {})
        ctx = self.build_context(neo)
        loop = asyncio.get_event_loop()

        try:
            result = await loop.run_in_executor(
                None,
                lambda: self.execute_tool_sync(name, args, ctx),
            )
        except Exception as e:
            traceback.print_exc()
            result = ToolResult(ok=False, text=f"Tool '{name}' failed: {e}", tool_name=name)
            if hasattr(neo, "speak_error"):
                neo.speak_error(name, e)

        if on_finish:
            on_finish(name, result)

        payload = result.text
        if len(payload) > 2400:
            payload = payload[:2400] + "… (truncated for live session)"

        response_body: dict = {"result": payload}
        if result.data.get("silent"):
            response_body["silent"] = True

        return types.FunctionResponse(id=fc.id, name=name, response=response_body)
