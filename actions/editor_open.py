"""Open projects in VS Code / Cursor and bring them to the front (macOS-friendly)."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


def _run(cmd: list[str], timeout: int = 8) -> bool:
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode == 0
    except Exception as e:
        print(f"[EditorOpen] {cmd[0]} failed: {e}")
        return False


def _activate_app(app_name: str) -> None:
    if sys.platform != "darwin":
        return
    script = f'tell application "{app_name}" to activate'
    subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)


def open_project_folder(project_dir: Path) -> tuple[bool, str]:
    """Open folder in VS Code/Cursor using app_resolver for dynamic discovery."""
    project_dir = Path(project_dir).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    path = str(project_dir)

    # Try app_resolver first — discovers editors dynamically
    try:
        from actions.app_resolver import resolve
        for editor_name in ("code", "cursor", "visual studio code", "vscode"):
            target = resolve(editor_name)
            if target:
                if target.kind == "exe":
                    subprocess.Popen(
                        [target.value, path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    time.sleep(1.2)
                    eid = "cursor" if "cursor" in target.label.lower() else "vscode"
                    print(f"[EditorOpen] Resolved {target.label} ({target.kind}), opened {path}")
                    return True, eid
                elif target.kind == "lnk":
                    subprocess.Popen(
                        [target.value, path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    time.sleep(1.2)
                    eid = "cursor" if "cursor" in target.label.lower() else "vscode"
                    return True, eid
    except Exception as e:
        print(f"[EditorOpen] app_resolver failed: {e}")

    # Fallback: OS-specific paths
    if sys.platform == "darwin":
        _run(["open", path])
        for app, eid in (
            ("Visual Studio Code", "vscode"),
            ("Cursor", "cursor"),
            ("Code", "vscode"),
        ):
            if _run(["open", "-a", app, path]):
                time.sleep(0.8)
                _activate_app(app)
                print(f"[EditorOpen] Opened in {app}: {path}")
                return True, eid
        cli_paths = ["/usr/local/bin/code"]
        for cli in cli_paths:
            if Path(cli).exists() and _run([cli, path]):
                time.sleep(0.8)
                _activate_app("Visual Studio Code")
                return True, "vscode"
        print(f"[EditorOpen] No editor found - opened Finder: {path}")
        return False, ""

    if sys.platform == "win32":
        if _run(["code", path]):
            return True, "vscode"
        return False, ""

    if _run(["code", path]):
        return True, "vscode"
    return False, ""
def open_terminal_run(project_dir: Path, command: str) -> None:
    """Open Terminal in project folder with optional run command."""
    if not command:
        return
    path = str(Path(project_dir).resolve())
    
    try:
        import sys
        import shutil
        if sys.platform == "darwin":
            safe_cmd = command.replace('"', '\\"')
            script = (
                f'tell application "Terminal"\n'
                f'  activate\n'
                f'  do script "cd \\"{path}\\" && {safe_cmd}"\n'
                f'end tell'
            )
            subprocess.run(["osascript", "-e", script], timeout=8)
            print(f"[EditorOpen] Terminal (macOS): cd {path} && {command}")
            
        elif sys.platform == "win32":
            cmd_args = ["cmd", "/c", "start", "cmd", "/K", f"cd /d \"{path}\" && {command}"]
            subprocess.run(cmd_args, timeout=8)
            print(f"[EditorOpen] Terminal (Windows): cd {path} && {command}")
            
        else:
            if shutil.which("gnome-terminal"):
                subprocess.run(["gnome-terminal", "--working-directory", path, "--", "bash", "-c", f"{command}; exec bash"], timeout=8, check=False)
            elif shutil.which("x-terminal-emulator"):
                subprocess.run(["x-terminal-emulator", "-e", f"bash -c 'cd \"{path}\" && {command}; exec bash'"], timeout=8, check=False)
            else:
                print(f"[EditorOpen] No supported terminal emulator found on Linux.")
                return
            print(f"[EditorOpen] Terminal (Linux): cd {path} && {command}")
            
    except Exception as e:
        print(f"[EditorOpen] Terminal open failed: {e}")


def copy_text_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard (macOS pbcopy)."""
    if not (text or "").strip():
        return False
    if sys.platform == "darwin":
        try:
            p = subprocess.run(
                ["pbcopy"],
                input=text,
                text=True,
                capture_output=True,
                timeout=5,
            )
            if p.returncode == 0:
                print("[EditorOpen] Copied VS Code AI prompt to clipboard")
                return True
        except Exception as e:
            print(f"[EditorOpen] pbcopy failed: {e}")
    elif sys.platform == "win32":
        try:
            subprocess.run(
                ["clip"],
                input=text,
                text=True,
                capture_output=True,
                timeout=5,
                check=True,
            )
            return True
        except Exception:
            pass
    return False


def open_prompt_in_editor(project_dir: Path, filename: str) -> bool:
    """Open a file inside the project in VS Code/Cursor using app_resolver."""
    path = Path(project_dir) / filename
    if not path.exists():
        return False
    full = str(path.resolve())

    # Try app_resolver first
    try:
        from actions.app_resolver import resolve
        for editor_name in ("code", "cursor", "visual studio code", "vscode"):
            target = resolve(editor_name)
            if target and target.kind in ("exe", "lnk"):
                subprocess.Popen(
                    [target.value, full],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(0.5)
                return True
    except Exception:
        pass

    # Fallback
    if sys.platform == "darwin":
        for app in ("Visual Studio Code", "Cursor", "Code"):
            if _run(["open", "-a", app, full]):
                time.sleep(0.5)
                _activate_app(app)
                return True
        if Path("/usr/local/bin/code").exists() and _run(["/usr/local/bin/code", full]):
            return True
    return _run(["code", full])
def open_static_preview(project_dir: Path, entry: str = "index.html") -> None:
    """Open HTML file in default browser."""
    p = Path(project_dir) / entry
    if not p.exists():
        return
    if sys.platform == "darwin":
        _run(["open", str(p)])
    elif sys.platform == "win32":
        _run(["start", "", str(p)])
    else:
        _run(["xdg-open", str(p)])

