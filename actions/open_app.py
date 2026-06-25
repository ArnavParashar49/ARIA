"""Open apps and sites — discovers what's installed on this machine, no app catalog."""

from __future__ import annotations

import platform
import subprocess
import time

from actions.app_resolver import (
    clear_index_cache,
    guess_web_url,
    launch,
    looks_like_url,
    resolve,
)

_SYSTEM = platform.system()


def _mac_spotlight_fallback(app_name: str) -> bool:
    """Spotlight search when the app index has no match."""
    try:
        r = subprocess.run(
            [
                "mdfind",
                f"(kMDItemKind == 'Application') && (kMDItemDisplayName == '*{app_name}*'cd)",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in (r.stdout or "").strip().splitlines():
            if line.endswith(".app"):
                subprocess.run(["open", line], timeout=10)
                time.sleep(0.8)
                return True
    except Exception as e:
        print(f"[open_app] Spotlight fallback: {e}")
    return False


def open_app(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    # Accept common aliases the model may pass instead of `app_name`
    app_name = (
        params.get("app_name")
        or params.get("name")
        or params.get("app")
        or params.get("application")
        or ""
    ).strip()
    if not app_name:
        return "No application name provided."

    if player:
        player.write_log(f"[open_app] {app_name}")

    # URLs go straight to the browser — no lookup table.
    if looks_like_url(app_name):
        from actions.browser_native import navigate_user_browser

        url = guess_web_url(app_name) or app_name
        print(f"[open_app] URL: {app_name} → {url}")
        navigate_user_browser(url)
        return f"Opened {app_name}."

    target = resolve(app_name)
    if target:
        print(
            f"[open_app] Resolved: {app_name!r} → {target.label!r} "
            f"({target.kind}, score={target.score})"
        )
        if launch(target):
            return f"Opened {target.label}."

    # macOS: one more try via Spotlight (dynamic, not hardcoded).
    if _SYSTEM == "Darwin" and _mac_spotlight_fallback(app_name):
        return f"Opened {app_name}."

    # Generic web fallback for single-word names (youtube → youtube.com).
    web = guess_web_url(app_name)
    if web:
        from actions.browser_native import navigate_user_browser

        print(f"[open_app] No install match — trying {web}")
        navigate_user_browser(web)
        return (
            f"Couldn't find {app_name} installed, so I opened {web} in your browser."
        )

    clear_index_cache()
    return (
        f"Couldn't find {app_name} on this PC. "
        f"It may not be installed."
    )