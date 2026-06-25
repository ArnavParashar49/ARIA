"""Verification agent — validates results and suggests retry."""

from __future__ import annotations

from hybrid.agents.base import BaseAgent
from hybrid.types import AgentRole, AgentTask, ExecutionContext, ToolResult


class VerificationAgent(BaseAgent):
    role = AgentRole.VERIFICATION

    def can_handle(self, task: AgentTask) -> bool:
        return task.mode.value == "planned" or "verify" in task.context

    def run(self, task: AgentTask, ctx: ExecutionContext) -> ToolResult:
        import os
        import subprocess

        # If there's code to verify, test it in the sandbox
        code_to_verify = task.context.get("code_to_verify")
        if code_to_verify:
            from core.paths import base_dir

            sandbox_dir = str(base_dir() / "sandbox")
            os.makedirs(sandbox_dir, exist_ok=True)
            test_file = os.path.join(sandbox_dir, "test_script.py")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(code_to_verify)
            
            try:
                result = subprocess.run(
                    ["python", test_file],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd=sandbox_dir
                )
                if result.returncode != 0:
                    self.emit("agent_handoff", {"status": "error", "error": f"Verification failed:\n{result.stderr}"})
                    return ToolResult(ok=False, text=f"Code failed in sandbox: {result.stderr}", tool_name="verify")
                return ToolResult(ok=True, text=f"Code passed sandbox execution: {result.stdout}", tool_name="verify")
            except subprocess.TimeoutExpired:
                return ToolResult(ok=False, text="Code execution timed out in sandbox", tool_name="verify")

        results = task.step_results
        if not results:
            return ToolResult(ok=False, text="No step results to verify.", tool_name="verify")

        failed = [
            n for n, txt in results.items()
            if str(txt).lower().startswith(("failed", "error", "could not"))
        ]
        if failed:
            return ToolResult(
                ok=False,
                text=f"Steps {failed} may have failed. Consider retry.",
                tool_name="verify",
            )

        previews = [str(v)[:80] for v in list(results.values())[:3]]
        summary = " | ".join(previews)
        return ToolResult(ok=True, text=f"Verified {len(results)} step(s). {summary}", tool_name="verify")
