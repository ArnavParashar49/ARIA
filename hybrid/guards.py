"""Tool guards — policy checks without hardcoding in the orchestrator."""

from __future__ import annotations

import re

from hybrid.types import ExecutionContext

_SCREEN_INTENT_RE = re.compile(
    r"\b("
    r"screen|display|monitor|webcam|camera|"
    r"what(?:'s| is| am i) (?:on |looking at |showing on |holding)|"
    r"what am i holding|what(?:'s| is) (?:this|that) (?:thing|object)|"
    r"identify (?:the |this |what )|"
    r"what do you see|what can you see|can you see|"
    r"look at (?:my |the )?(?:screen|display|monitor|this|camera|webcam)|"
    r"on my screen|see (?:my |the )?screen|through the camera|"
    r"read (?:my |the )?screen|describe (?:my |the )?screen|"
    r")\b",
    re.I,
)


def allow_screen_process(args: dict, ctx: ExecutionContext) -> str | None:
    """Return error message if screen_process should be blocked."""
    q = (args.get("text") or args.get("user_text") or "").strip()
    combined = f"{ctx.last_user_log} {q}".strip()
    if _SCREEN_INTENT_RE.search(combined):
        return None
    return (
        "Screen capture skipped — this did not sound like a screen or "
        "camera question. Use web_search for general information."
    )
