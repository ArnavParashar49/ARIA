"""Browser automation tool (Playwright). Split into _helpers (URL / profile /
browser detection), _session (the stateful browser session + registry), and
this dispatcher. Re-exports browser_control, _registry, and _app_download_hint
for sibling modules (browser_native, download_control) that import them."""

from __future__ import annotations

import concurrent.futures

from actions.browser_control._helpers import (
    _OS, _USE_NATIVE_NAV, _app_download_hint, _BAD_RESULT_DOMAINS,
    _BROWSER_SPECS, _ALIASES,
    _normalize_url, _native_navigate, _user_agent, _real_profile_dir,
    _firefox_profile_dir, _find_opera_windows, _find_exe_windows,
    _resolve_browser, _detect_default_browser,
)
from actions.browser_control._session import (
    _BrowserSession, _SessionRegistry, _registry,
)


def browser_control(
    parameters:    dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params  = parameters or {}
    # Accept model-friendly aliases for the action
    action_raw = (
        params.get("action")
        or params.get("go_to")
        or params.get("do")
        or params.get("navigate")
        or ""
    )
    action = action_raw.lower().strip()
    # If the action is itself a URL, treat it as go_to
    if action.startswith("http"):
        action = "go_to"
        params.setdefault("url", action_raw)
    # If url is provided but action is missing/empty, default to go_to
    if not action and params.get("url"):
        action = "go_to"
    # If neither action nor url, fail helpfully
    if not action and not params.get("url"):
        return "browser_control needs an action (e.g. 'go_to') or a url."
    browser = params.get("browser", "").lower().strip() or None
    result  = "Unknown action."

    if action == "switch":
        target = browser or params.get("target", "").lower().strip()
        result = _registry.switch(target) if target else "Please specify a browser."
        _log(player, result)
        return result

    if action == "list_browsers":
        result = _registry.list_sessions()
        _log(player, result)
        return result

    if action == "close_all":
        result = _registry.close_all()
        _log(player, result)
        return result

    # Navigation-only: use real browser — never spin up Playwright (avoids about:blank window).
    if _USE_NATIVE_NAV and action == "go_to":
        url = params.get("url") or action_raw
        result = _native_navigate(url, browser)
        _log(player, result)
        return result

    if _USE_NATIVE_NAV and action == "search":
        from actions.browser_native import is_visual_product_query
        from config import DEFAULT_SEARCH_ENGINE, search_engine_url

        engine = (params.get("engine") or DEFAULT_SEARCH_ENGINE).lower()
        query = params.get("query", "")
        url = search_engine_url(query, engine, images=is_visual_product_query(query))
        result = _native_navigate(url, browser)
        _log(player, result)
        return result

    if _USE_NATIVE_NAV and action == "new_tab" and params.get("url"):
        result = _native_navigate(params.get("url", ""), browser)
        _log(player, result)
        return result

    try:
        sess = _registry.get(browser)
    except Exception as e:
        result = f"Could not start browser session: {e}"
        _log(player, result)
        return result

    try:
        if action == "go_to":
            result = sess.run(sess.go_to(params.get("url", "")))
        elif action == "search":
            from config import DEFAULT_SEARCH_ENGINE

            result = sess.run(sess.search(
                params.get("query", ""),
                params.get("engine", DEFAULT_SEARCH_ENGINE),
            ))
        elif action == "click":
            result = sess.run(sess.click(params.get("selector"), params.get("text")))
        elif action == "type":
            result = sess.run(sess.type_text(
                params.get("selector"), params.get("text", ""), params.get("clear_first", True)))
        elif action == "scroll":
            result = sess.run(sess.scroll(params.get("direction", "down"), int(params.get("amount", 500))))
        elif action == "fill_form":
            result = sess.run(sess.fill_form(params.get("fields", {})))
        elif action == "smart_click":
            result = sess.run(sess.smart_click(params.get("description", "")))
        elif action == "smart_type":
            result = sess.run(sess.smart_type(params.get("description", ""), params.get("text", "")))
        elif action == "get_text":
            result = sess.run(sess.get_text())
        elif action == "get_url":
            result = sess.run(sess.get_url())
        elif action == "press":
            result = sess.run(sess.press(params.get("key", "Enter")))
        elif action == "new_tab":
            result = sess.run(sess.new_tab(params.get("url", "")))
        elif action == "close_tab":
            result = sess.run(sess.close_tab())
        elif action == "screenshot":
            result = sess.run(sess.screenshot(params.get("path")))
        elif action == "back":
            result = sess.run(sess.back())
        elif action == "forward":
            result = sess.run(sess.forward())
        elif action == "reload":
            result = sess.run(sess.reload())
        elif action == "close":
            target = browser or _registry._active_browser
            result = _registry.close_one(target) if target else "No browser specified."
        else:
            result = f"Unknown browser action: '{action}'"

    except concurrent.futures.TimeoutError:
        result = f"Browser action '{action}' timed out (60s)."
    except Exception as e:
        result = f"Browser error ({action}): {e}"

    _log(player, result)
    return result


def _log(player, text: str):
    short = str(text)[:80]
    print(f"[Browser] {short}")
    if player:
        player.write_log(f"[browser] {short[:60]}")