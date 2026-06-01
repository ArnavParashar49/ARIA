# ARIA Hybrid Agent Architecture

## Design principle

**Adaptive routing** — not every request runs the planner or multiple LLM calls.

| Path | When | LLM calls | Latency target |
|------|------|-----------|----------------|
| **Fast** | Open app, volume, Bluetooth, play music | 0 extra (regex router) | &lt; 1s |
| **Direct** | Gemini picks a single tool | 0 extra (live model already understood NL) | Tool time only |
| **Planned** | Multi-step goals, `agent_task`, complex regex | 1 planner + optional executor | Accuracy over speed |

## Flow diagrams

### Fast path (typed command or matched utterance)

```
User → Orchestrator.try_fast_path() → Router (regex)
     → SystemAgent / ToolAgent → ToolRegistry → action handler → Response
```

### Direct path (voice/text via Gemini Live)

```
User → Gemini Live (1 session) → function_call
     → Orchestrator.execute_tool_for_live() → ToolRegistry → Response
```

### Planned path

```
User → Orchestrator.run_planned_sync()
     → PlannerAgent (create_plan — 1 LLM)
     → Parallel independent steps → dependent steps
     → VerificationAgent → Response
```

## Components

| Module | Role |
|--------|------|
| `orchestrator.py` | Entry point, routing, agent dispatch |
| `router.py` | Fast vs planned classification (no LLM) |
| `registry.py` | Dynamic tool metadata + handlers |
| `task_bus.py` | Structured pub/sub between agents |
| `types.py` | `AgentTask`, `RouteDecision`, `ExecutionContext` |
| `bootstrap.py` | Registers all tools at startup |
| `declarations.py` | Gemini function schemas |
| `agents/*` | Specialized agents (thin wrappers over registry) |

## Adding a new tool (no orchestrator edits)

1. Implement `actions/my_tool.py` with `my_tool(parameters, player=None) -> str`.
2. Add schema to `hybrid/declarations.py` (`TOOL_DECLARATIONS`).
3. Add handler in `hybrid/bootstrap.py` → `_build_handlers()` and optional `_TOOL_META`.
4. Restart ARIA — `register_all_tools()` picks it up automatically.

Optional: set `"agent": "device"` in `_TOOL_META` for IoT tools handled by `DeviceAgent`.

## Agent responsibilities

- **Orchestrator** — context, routing, execution, task state
- **PlannerAgent** — `agent.planner.create_plan`
- **ToolExecutionAgent** — default registry invoke
- **SystemAgent** — OS, files, apps, dev tools
- **ResearchAgent** — web, vision, weather
- **MemoryAgent** — `save_memory`, contacts
- **DeviceAgent** — isolated IoT extension point
- **VerificationAgent** — step result checks before final reply

## Configuration

In `config/api_keys.json`:

```json
"hybrid_fast_path": true
```

When true, typed commands in the UI try regex fast path before sending to Gemini Live.

## Integration point

`main.py` → `AriaLive._execute_tool` delegates to `get_orchestrator().execute_tool_for_live()`.

Legacy `agent/` package remains for background `TaskQueue` and executor replanning.
