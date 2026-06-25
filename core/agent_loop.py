"""Autonomous tool-use loop (ReAct-style) for NEO.

Instead of routing by regex or pre-planning a fixed list of independent steps,
this gives the model a goal + the live tool schemas and lets it decide the next
action, observe the *real* result, and decide again — until the goal is met.

Design:
- The loop logic (`run_agent`) is SDK-free and depends on a small `ToolSession`
  interface, so it can be unit-tested with a fake session (no network).
- `GeminiToolSession` is the only piece that touches the google.genai SDK.
- Safety is structural, not prompt-dependent:
    * a hard step budget,
    * a repeated-identical-call guard (kills thrash loops),
    * a deterministic human-in-the-loop STOP whenever a tool returns
      NEEDS_CONFIRM / NEEDS_USER — the loop never auto-confirms destructive ops.

Enable it by setting ``"autonomous_mode": true`` in config/api_keys.json; until
then the existing planner path is used and this module is dormant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from hybrid.registry import ToolRegistry
from hybrid.types import ExecutionContext

from core.models import PRIMARY as DEFAULT_AGENT_MODEL
DEFAULT_MAX_STEPS = 12

# Cap a single tool result fed back into context. Long dev_run logs would
# otherwise crowd out the plan and earlier files, making flash lose the thread.
_MAX_RESULT_CHARS = 4000

# Tool results that must halt the loop and hand control back to the human.
_STOP_PREFIXES = ("NEEDS_CONFIRM", "NEEDS_USER")

AGENT_SYSTEM_PROMPT = """You are NEO's autonomous task agent.

You are given a goal and a set of tools. Work toward the goal by deciding ONE next
action at a time: call the most appropriate tool, observe the real result, then
decide the next action based on what actually happened.

Principles:
- Use real tool results — never assume a tool succeeded; read its output.
- Prefer the fewest actions that fully achieve the goal.
- After each result, check whether the goal is met. If it is, STOP and reply with a
  short, natural summary (no tool call).
- If a tool fails, adapt — try a different tool or approach. Do not repeat the same
  failing call.
- If a tool result says NEEDS_CONFIRM or NEEDS_USER, do not try to work around it —
  stop and let the user decide.
- If you are missing information only the user can provide, ask one concise question
  instead of guessing.
"""


# --------------------------------------------------------------------------- #
# Results & the session interface the loop depends on                          #
# --------------------------------------------------------------------------- #

@dataclass
class Step:
    tool: str
    args: dict[str, Any]
    result: str
    ok: bool


@dataclass
class AgentResult:
    answer: str
    steps: list[Step] = field(default_factory=list)
    stopped_reason: str = "done"  # done | max_steps | needs_user | loop_guard


@dataclass
class Turn:
    """One decision from the model: either tool calls, or a final text answer."""
    calls: list[tuple[str, dict]] = field(default_factory=list)
    text: str | None = None


class ToolSession(Protocol):
    def step(self) -> Turn: ...
    def add_tool_result(self, name: str, result: str) -> None: ...
    def finalize(self) -> str: ...


# --------------------------------------------------------------------------- #
# The loop — no SDK, fully testable                                            #
# --------------------------------------------------------------------------- #

def run_agent(
    goal: str,
    ctx: ExecutionContext | None = None,
    *,
    registry: ToolRegistry | None = None,
    session: ToolSession | None = None,
    max_steps: int = DEFAULT_MAX_STEPS,
    on_step: Callable[[Step], None] | None = None,
) -> AgentResult:
    registry = registry or ToolRegistry.instance()
    ctx = ctx or ExecutionContext()
    if session is None:
        try:
            from core.memory_rag import format_memory_for_prompt
            memory_context = format_memory_for_prompt(goal)
        except ImportError:
            memory_context = ""
            
        full_system = AGENT_SYSTEM_PROMPT
        if memory_context:
            full_system += f"\n\n{memory_context}"

        session = GeminiToolSession(
            goal,
            system=full_system,
            tools=registry.to_gemini_declarations(),
        )

    steps: list[Step] = []
    call_counts: dict[tuple[str, str], int] = {}

    for _ in range(max_steps):
        turn = session.step()

        if not turn.calls:
            return AgentResult(answer=(turn.text or "").strip(), steps=steps, stopped_reason="done")

        for name, args in turn.calls:
            args = dict(args or {})

            # Loop guard: the same call 3x means the model is thrashing.
            sig = (name, repr(sorted(args.items())))
            call_counts[sig] = call_counts.get(sig, 0) + 1
            if call_counts[sig] > 3:
                return AgentResult(
                    answer=f"Stopping: '{name}' was called repeatedly without progress.",
                    steps=steps,
                    stopped_reason="loop_guard",
                )

            result = registry.invoke(name, args, ctx)
            step = Step(tool=name, args=args, result=result.text, ok=result.ok)
            steps.append(step)
            if on_step:
                on_step(step)

            # Human-in-the-loop: never auto-confirm destructive actions.
            if result.text.strip().startswith(_STOP_PREFIXES):
                return AgentResult(answer=result.text, steps=steps, stopped_reason="needs_user")

            session.add_tool_result(name, result.text)

    # Ran out of budget — ask the model to summarize where it landed.
    try:
        final = session.finalize()
    except Exception:
        final = "Reached the action limit before fully completing the goal."
    return AgentResult(answer=final, steps=steps, stopped_reason="max_steps")


# --------------------------------------------------------------------------- #
# Gemini glue — the only SDK-aware piece                                       #
# --------------------------------------------------------------------------- #

class GeminiToolSession:
    """A stateful function-calling conversation against litellm."""

    def __init__(
        self,
        goal: str,
        *,
        system: str,
        tools: list[dict],
        model: str = DEFAULT_AGENT_MODEL,
        temperature: float | None = None,
        thinking_budget: int | None = None,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._thinking_budget = thinking_budget
        
        # Tools in litellm format (OpenAI format)
        self._tools = [{"type": "function", "function": t} for t in tools] if tools else None
        
        self._messages: list[dict] = []
        if system:
            self._messages.append({"role": "system", "content": system})
        self._messages.append({"role": "user", "content": goal})

    def _generate(self, *, with_tools: bool = True):
        import time
        import litellm
        from core.llm import _get_api_key_for_model
        
        kwargs = {
            "model": self._model,
            "messages": self._messages,
        }
        
        # litellm expects gemini models to have gemini/ prefix
        if kwargs["model"].startswith("gemini-"):
            kwargs["model"] = f"gemini/{kwargs['model']}"
            
        api_key = _get_api_key_for_model(kwargs["model"])
        if api_key:
            kwargs["api_key"] = api_key
            
        if with_tools and self._tools:
            kwargs["tools"] = self._tools
            
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature

        last: Exception | None = None
        for attempt in range(3):
            try:
                return litellm.completion(**kwargs)
            except Exception as e:
                last = e
                msg = str(e)
                if not any(code in msg for code in ("429", "503", "500", "UNAVAILABLE")):
                    raise
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        raise last

    def step(self) -> Turn:
        resp = self._generate()
        msg = resp.choices[0].message
        
        # litellm returns message dict-like object
        calls = []
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            import json
            for tc in msg.tool_calls:
                args = {}
                if hasattr(tc.function, "arguments"):
                    try:
                        args = json.loads(tc.function.arguments)
                    except Exception:
                        if isinstance(tc.function.arguments, dict):
                            args = tc.function.arguments
                calls.append((tc.function.name, args))
                
            self._messages.append(msg.model_dump())
            return Turn(calls=calls)
            
        self._messages.append(msg.model_dump())
        return Turn(text=msg.content or "")

    def add_tool_result(self, name: str, result: str) -> None:
        text = result or ""
        if len(text) > _MAX_RESULT_CHARS:
            head = text[: _MAX_RESULT_CHARS // 2]
            tail = text[-_MAX_RESULT_CHARS // 2 :]
            text = f"{head}\n…[{len(result) - _MAX_RESULT_CHARS} chars trimmed]…\n{tail}"
            
        # Find the tool_call_id for this name from the last assistant message
        tool_call_id = "unknown"
        for m in reversed(self._messages):
            if m.get("role") == "assistant" and m.get("tool_calls"):
                for tc in m.get("tool_calls"):
                    func = tc.get("function") if isinstance(tc, dict) else getattr(tc, "function", None)
                    func_name = func.get("name") if isinstance(func, dict) else getattr(func, "name", None)
                    if func_name == name:
                        tool_call_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "unknown")
                        break
                if tool_call_id != "unknown":
                    break
                    
        import json
        self._messages.append({
            "role": "tool",
            "tool_call_id": str(tool_call_id),
            "name": name,
            "content": json.dumps({"result": text})
        })

    def finalize(self) -> str:
        self._messages.append({
            "role": "user",
            "content": "You've hit the action limit. In one or two sentences, summarize what you accomplished and what (if anything) remains."
        })
        resp = self._generate(with_tools=False)
        return (resp.choices[0].message.content or "Reached the action limit.").strip()



