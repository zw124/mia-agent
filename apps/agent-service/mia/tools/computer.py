import re
import os
import json
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from langchain_core.tools import StructuredTool

from mia.integrations.convex import ConvexClient

PROJECT_ROOT = Path(__file__).resolve().parents[4]
MIA_RUNTIME_DIR = PROJECT_ROOT / ".mia"
SCREENSHOT_DIR = MIA_RUNTIME_DIR / "screenshots"
PROCESS_LOG_DIR = MIA_RUNTIME_DIR / "processes"
MANAGED_PROCESSES: dict[str, subprocess.Popen[str]] = {}
AUTO_APPROVE_NUMBERS: set[str] = set()
AUTO_APPROVABLE_ACTION_KINDS = {
    "open_app",
    "click_screen",
    "type_text",
    "press_key",
    "scroll",
    "set_clipboard",
    "show_notification",
    "speak_text",
}
HARD_CONFIRM_ACTION_KINDS = {
    "run_terminal_command",
    "process_start",
    "process_kill",
    "send_imessage",
    "create_reminder",
    "write_file",
    "append_file",
    "replace_in_file",
    "delete_file",
    "create_directory",
    "copy_file",
    "move_file",
}


KNOWN_SITES = {
    "wikipedia": "https://www.wikipedia.org",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
}


def resolve_url(target: str) -> str:
    cleaned = target.strip()
    lowered = cleaned.lower()
    for name, url in KNOWN_SITES.items():
        if name in lowered:
            return url

    match = re.search(r"https?://[^\s]+", cleaned)
    if match:
        url = match.group(0).rstrip(".,)")
    else:
        domain = lowered.strip(" .")
        if not domain:
            raise ValueError("No URL or known website was provided")
        url = f"https://{domain}"

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Only http and https URLs are allowed")
    return url


def _pending_reply(code: str, summary: str) -> str:
    return f"Do you approve?\n{summary}\nReply approve to run it."


def enable_auto_approve(number: str) -> None:
    if number:
        AUTO_APPROVE_NUMBERS.add(number)


def disable_auto_approve(number: str) -> None:
    AUTO_APPROVE_NUMBERS.discard(number)


def is_auto_approve_enabled(number: str) -> bool:
    return number in AUTO_APPROVE_NUMBERS


def auto_approve_status(number: str) -> str:
    if is_auto_approve_enabled(number):
        return (
            "Auto approve is on for low-risk computer actions. "
            "Terminal commands, background processes, and file mutations still ask first."
        )
    return "Auto approve is off."


async def _create_pending_action(
    convex: ConvexClient | None,
    *,
    requester_number: str,
    message_handle: str,
    run_id: str | None,
    kind: str,
    summary: str,
    payload: dict[str, Any],
    risk: str = "approval_required",
) -> str:
    if convex is None:
        return "Approval backend is unavailable."
    code = await convex.create_pending_action(
        requester_number=requester_number,
        message_handle=message_handle,
        run_id=run_id,
        kind=kind,
        summary=summary,
        payload=payload,
        risk=risk,
    )
    if is_auto_approve_enabled(requester_number) and kind in AUTO_APPROVABLE_ACTION_KINDS:
        action = {
            "code": code,
            "kind": kind,
            "payload": payload,
        }
        try:
            result = execute_pending_action(action)
            await convex.complete_pending_action(
                code=code,
                requester_number=requester_number,
                result=result,
            )
            return f"Auto approved and completed:\n{result[:1200]}"
        except Exception as exc:
            await convex.fail_pending_action(
                code=code,
                requester_number=requester_number,
                error=str(exc),
            )
            return f"Auto approve tried to run it, but it failed: {exc}"
    if is_auto_approve_enabled(requester_number) and kind in HARD_CONFIRM_ACTION_KINDS:
        return (
            f"Do you approve?\n{summary}\n"
            "Auto approve is on, but this action can change files, run commands, or manage processes. "
            "Reply approve to run it."
        )
    return _pending_reply(code, summary)


def _run_osascript(script: str) -> str:
    try:
        completed = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            text=True,
            capture_output=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(
            "macOS blocked this action. Grant Terminal/Python permission in System Settings "
            f"if prompted, then ask Mia to retry. Details: {detail}"
        ) from exc
    return completed.stdout.strip()


def _safe_read_text(path: Path, limit: int = 12000) -> str:
    content = path.read_text(errors="replace")
    return content[:limit]


def _normalize_file_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _execute_click_screen(x: int, y: int, button: str = "left") -> str:
    if button != "left":
        raise ValueError("Only left click is currently supported on macOS")
    script = f'tell application "System Events" to click at {{{int(x)}, {int(y)}}}'
    _run_osascript(script)
    return f"Clicked screen at x={int(x)} y={int(y)}"


def _execute_type_text(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    _run_osascript(f'tell application "System Events" to keystroke "{escaped}"')
    return f"Typed {len(text)} character(s)"


KEY_CODE_MAP = {
    "return": 36,
    "enter": 36,
    "tab": 48,
    "space": 49,
    "delete": 51,
    "escape": 53,
    "esc": 53,
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
}

MODIFIER_MAP = {
    "cmd": "command down",
    "command": "command down",
    "shift": "shift down",
    "option": "option down",
    "alt": "option down",
    "control": "control down",
    "ctrl": "control down",
}


def _execute_press_key(key: str, modifiers: list[str] | None = None) -> str:
    normalized_key = key.strip().lower()
    normalized_modifiers = [modifier.strip().lower() for modifier in modifiers or [] if modifier.strip()]
    modifier_tokens = [MODIFIER_MAP[modifier] for modifier in normalized_modifiers if modifier in MODIFIER_MAP]
    using_clause = f" using {{{', '.join(modifier_tokens)}}}" if modifier_tokens else ""
    if len(normalized_key) == 1:
        escaped = normalized_key.replace("\\", "\\\\").replace('"', '\\"')
        _run_osascript(f'tell application "System Events" to keystroke "{escaped}"{using_clause}')
    elif normalized_key in KEY_CODE_MAP:
        _run_osascript(
            f'tell application "System Events" to key code {KEY_CODE_MAP[normalized_key]}{using_clause}'
        )
    else:
        raise ValueError(f"Unsupported key: {key}")
    label = "+".join([*normalized_modifiers, normalized_key]) if normalized_modifiers else normalized_key
    return f"Pressed {label}"


def _execute_scroll(amount: int) -> str:
    _run_osascript(f'tell application "System Events" to scroll {int(amount)}')
    return f"Scrolled {int(amount)} unit(s)"


def _execute_set_clipboard(text: str) -> str:
    subprocess.run(["pbcopy"], input=text, text=True, check=True, timeout=10)
    return f"Set clipboard to {len(text)} character(s)"


def _execute_show_notification(title: str, message: str) -> str:
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_message = message.replace("\\", "\\\\").replace('"', '\\"')
    _run_osascript(f'display notification "{safe_message}" with title "{safe_title}"')
    return f"Displayed notification: {title}"


def _execute_speak_text(text: str, voice: str = "") -> str:
    command = ["say"]
    if voice.strip():
        command.extend(["-v", voice.strip()])
    command.append(text)
    subprocess.run(command, check=True, timeout=120)
    return f"Spoke {len(text)} character(s)"


def _execute_process_start(command: str, cwd: str = "") -> str:
    PROCESS_LOG_DIR.mkdir(parents=True, exist_ok=True)
    process_id = f"proc-{int(time.time() * 1000)}"
    log_path = PROCESS_LOG_DIR / f"{process_id}.log"
    handle = log_path.open("w")
    process = subprocess.Popen(
        command,
        cwd=cwd or None,
        shell=True,
        text=True,
        stdin=subprocess.PIPE,
        stdout=handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    MANAGED_PROCESSES[process_id] = process
    return f"Started {process_id} pid={process.pid} log={log_path}"


def _execute_process_kill(process_id: str) -> str:
    process = MANAGED_PROCESSES.get(process_id)
    if process is None:
        return f"Unknown managed process: {process_id}"
    if process.poll() is not None:
        return f"{process_id} already exited with code {process.returncode}"
    try:
        pgid = os.getpgid(process.pid)
        os.killpg(pgid, signal.SIGTERM)
    except Exception:
        process.terminate()
    return f"Terminated {process_id}"


def build_computer_tools(
    convex: ConvexClient | None = None,
    *,
    requester_number: str = "",
    message_handle: str = "",
    run_id: str | None = None,
) -> list[StructuredTool]:
    async def open_url(target: str) -> str:
        url = resolve_url(target)
        subprocess.run(["open", url], check=True)
        return f"Opened {url}"

    async def get_frontmost_app() -> str:
        return _run_osascript(
            'tell application "System Events" to get name of first application process whose frontmost is true'
        )

    async def list_running_apps() -> str:
        output = _run_osascript(
            'tell application "System Events" to get name of every application process whose background only is false'
        )
        apps = [item.strip() for item in output.split(",") if item.strip()]
        return "\n".join(sorted(set(apps)))[:12000]

    async def screenshot_desktop(label: str = "") -> str:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        safe_label = re.sub(r"[^a-zA-Z0-9_.-]+", "-", label.strip())[:48] or "screen"
        path = SCREENSHOT_DIR / f"{int(time.time())}-{safe_label}.png"
        subprocess.run(["screencapture", "-x", str(path)], check=True, timeout=30)
        return f"Saved screenshot: {path}"

    async def read_file(path: str) -> str:
        file_path = _normalize_file_path(path)
        if not file_path.exists() or not file_path.is_file():
            return f"File not found: {file_path}"
        return _safe_read_text(file_path)

    async def list_directory(path: str = ".") -> str:
        directory = _normalize_file_path(path)
        if not directory.exists() or not directory.is_dir():
            return f"Directory not found: {directory}"
        rows = []
        for child in sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))[:300]:
            kind = "dir" if child.is_dir() else "file"
            rows.append(f"{kind}\t{child}")
        return "\n".join(rows)[:12000]

    async def file_info(path: str) -> str:
        target = _normalize_file_path(path)
        if not target.exists():
            return f"Path not found: {target}"
        stat = target.stat()
        kind = "directory" if target.is_dir() else "file"
        return "\n".join(
            [
                f"path: {target}",
                f"type: {kind}",
                f"size: {stat.st_size}",
                f"modified: {stat.st_mtime}",
                f"created: {stat.st_ctime}",
            ]
        )

    async def search_files(query: str, path: str = ".", max_results: int = 50) -> str:
        directory = _normalize_file_path(path)
        if not directory.exists() or not directory.is_dir():
            return f"Directory not found: {directory}"
        if not query.strip():
            return "Missing search query."
        completed = subprocess.run(
            ["rg", "--files", str(directory)],
            check=False,
            text=True,
            capture_output=True,
            timeout=30,
        )
        if completed.returncode not in {0, 1}:
            return completed.stderr.strip()[:12000] or "File search failed."
        lowered_query = query.lower()
        matches = [
            line
            for line in completed.stdout.splitlines()
            if lowered_query in Path(line).name.lower() or lowered_query in line.lower()
        ][: max(1, min(max_results, 200))]
        return "\n".join(matches) if matches else "No matching files found."

    async def fetch_webpage(url: str) -> str:
        resolved = resolve_url(url)
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(
                resolved,
                headers={"user-agent": "MiaAgent/0.1 (+local personal agent)"},
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            text = response.text
        return f"URL: {response.url}\nContent-Type: {content_type}\n\n{text[:12000]}"

    async def web_fetch(url: str) -> str:
        return await fetch_webpage(url)

    async def get_clipboard() -> str:
        completed = subprocess.run(
            ["pbpaste"],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        return completed.stdout[:12000]

    async def image_info(path: str) -> str:
        target = _normalize_file_path(path)
        if not target.exists() or not target.is_file():
            return f"Image not found: {target}"
        completed = subprocess.run(
            ["sips", "-g", "all", str(target)],
            text=True,
            capture_output=True,
            check=False,
            timeout=20,
        )
        output = completed.stdout.strip() or completed.stderr.strip()
        return output[:12000]

    async def image(path: str) -> str:
        return await image_info(path)

    async def extract_pdf_text(path: str) -> str:
        target = _normalize_file_path(path)
        if not target.exists() or not target.is_file():
            return f"PDF not found: {target}"
        if shutil.which("pdftotext"):
            completed = subprocess.run(
                ["pdftotext", "-layout", str(target), "-"],
                text=True,
                capture_output=True,
                check=False,
                timeout=60,
            )
            return (completed.stdout.strip() or completed.stderr.strip())[:12000]
        completed = subprocess.run(
            ["mdls", "-raw", "-name", "kMDItemTextContent", str(target)],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        output = completed.stdout.strip()
        if not output or output == "(null)":
            return "PDF text extraction backend unavailable. Install poppler for pdftotext."
        return output[:12000]

    async def pdf(path: str) -> str:
        return await extract_pdf_text(path)

    async def process_list() -> str:
        rows = []
        for process_id, process in sorted(MANAGED_PROCESSES.items()):
            status = "running" if process.poll() is None else f"exited:{process.returncode}"
            rows.append(f"{process_id}\tpid={process.pid}\t{status}")
        return "\n".join(rows) if rows else "No managed processes."

    async def process_read(process_id: str, max_chars: int = 12000) -> str:
        log_path = PROCESS_LOG_DIR / f"{process_id}.log"
        if not log_path.exists():
            return f"Log not found for {process_id}"
        content = log_path.read_text(errors="replace")
        limit = max(1000, min(max_chars, 50000))
        return content[-limit:]

    async def process(action: str = "list", process_id: str = "", max_chars: int = 12000) -> str:
        if action == "list":
            return await process_list()
        if action in {"read", "poll"}:
            return await process_read(process_id, max_chars)
        if action == "kill":
            return await request_process_kill(process_id)
        return "Supported process actions: list, read, poll, kill."

    async def gateway(action: str = "status") -> str:
        if action not in {"status", "heartbeat"}:
            return "Supported gateway actions: status, heartbeat."
        heartbeat_path = MIA_RUNTIME_DIR / "heartbeat.json"
        if not heartbeat_path.exists():
            return "Mia gateway heartbeat has not written state yet."
        return heartbeat_path.read_text(errors="replace")[:12000]

    async def sessions_list() -> str:
        return await process_list()

    async def sessions_history() -> str:
        if not PROCESS_LOG_DIR.exists():
            return "No Mia-managed process history."
        rows = []
        for log_path in sorted(PROCESS_LOG_DIR.glob("*.log"), key=lambda item: item.stat().st_mtime, reverse=True)[:50]:
            rows.append(f"{log_path.stem}\tmodified={log_path.stat().st_mtime}\tpath={log_path}")
        return "\n".join(rows) if rows else "No Mia-managed process history."

    async def request_terminal_command(command: str, cwd: str = "") -> str:
        summary = f"Run terminal command: {command}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="run_terminal_command",
            summary=summary,
            payload={"command": command, "cwd": cwd},
            risk="approval_required",
        )

    async def request_exec(command: str, cwd: str = "") -> str:
        return await request_terminal_command(command, cwd)

    async def request_write_file(path: str, content: str) -> str:
        summary = f"Write file: {path}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="write_file",
            summary=summary,
            payload={"path": path, "content": content},
            risk="approval_required",
        )

    async def request_write(path: str, content: str) -> str:
        return await request_write_file(path, content)

    async def request_delete_file(path: str) -> str:
        summary = f"Delete file: {path}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="delete_file",
            summary=summary,
            payload={"path": path},
            risk="approval_required",
        )

    async def request_append_file(path: str, content: str) -> str:
        summary = f"Append to file: {path}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="append_file",
            summary=summary,
            payload={"path": path, "content": content},
            risk="approval_required",
        )

    async def request_replace_in_file(path: str, old: str, new: str) -> str:
        summary = f"Replace text in file: {path}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="replace_in_file",
            summary=summary,
            payload={"path": path, "old": old, "new": new},
            risk="approval_required",
        )

    async def request_edit(path: str, old: str, new: str) -> str:
        return await request_replace_in_file(path, old, new)

    async def request_apply_patch(patch: str) -> str:
        summary = "Apply patch to local workspace"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="run_terminal_command",
            summary=summary,
            payload={"command": f"apply_patch <<'PATCH'\n{patch}\nPATCH", "cwd": str(PROJECT_ROOT)},
            risk="approval_required",
        )

    async def request_create_directory(path: str) -> str:
        summary = f"Create directory: {path}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="create_directory",
            summary=summary,
            payload={"path": path},
            risk="approval_required",
        )

    async def request_copy_file(source: str, destination: str) -> str:
        summary = f"Copy file: {source} -> {destination}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="copy_file",
            summary=summary,
            payload={"source": source, "destination": destination},
            risk="approval_required",
        )

    async def request_move_file(source: str, destination: str) -> str:
        summary = f"Move file: {source} -> {destination}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="move_file",
            summary=summary,
            payload={"source": source, "destination": destination},
            risk="approval_required",
        )

    async def request_open_app(app_name: str) -> str:
        summary = f"Open application: {app_name}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="open_app",
            summary=summary,
            payload={"app_name": app_name},
            risk="approval_required",
        )

    async def request_set_clipboard(text: str) -> str:
        summary = f"Set clipboard ({len(text)} characters)"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="set_clipboard",
            summary=summary,
            payload={"text": text},
            risk="approval_required",
        )

    async def request_show_notification(title: str, message: str) -> str:
        summary = f"Show notification: {title}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="show_notification",
            summary=summary,
            payload={"title": title, "message": message},
            risk="approval_required",
        )

    async def request_speak_text(text: str, voice: str = "") -> str:
        summary = f"Speak text aloud ({len(text)} characters)"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="speak_text",
            summary=summary,
            payload={"text": text, "voice": voice},
            risk="approval_required",
        )

    async def request_process_start(command: str, cwd: str = "") -> str:
        summary = f"Start background process: {command}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="process_start",
            summary=summary,
            payload={"command": command, "cwd": cwd},
            risk="approval_required",
        )

    async def request_sessions_spawn(task: str, cwd: str = "") -> str:
        command = task
        summary = f"Spawn managed session: {command}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="process_start",
            summary=summary,
            payload={"command": command, "cwd": cwd},
            risk="approval_required",
        )

    async def request_process_kill(process_id: str) -> str:
        summary = f"Kill managed process: {process_id}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="process_kill",
            summary=summary,
            payload={"process_id": process_id},
            risk="approval_required",
        )

    async def request_send_imessage(number: str, content: str) -> str:
        summary = f"Send iMessage to {number}: {content[:120]}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="send_imessage",
            summary=summary,
            payload={"number": number, "content": content},
            risk="approval_required",
        )

    async def request_message(number: str, content: str) -> str:
        return await request_send_imessage(number, content)

    async def request_create_reminder(title: str, remind_at: str = "") -> str:
        summary = f"Create reminder: {title}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="create_reminder",
            summary=summary,
            payload={"title": title, "remind_at": remind_at},
            risk="approval_required",
        )

    async def request_cron(title: str, schedule: str = "") -> str:
        return await request_create_reminder(title, schedule)

    async def request_tts(text: str, voice: str = "") -> str:
        return await request_speak_text(text, voice)

    async def sessions_send(process_id: str, text: str) -> str:
        process = MANAGED_PROCESSES.get(process_id)
        if process is None or process.stdin is None:
            return f"Cannot send input to {process_id}; process is unknown or has no stdin pipe."
        process.stdin.write(text)
        process.stdin.flush()
        return f"Sent {len(text)} character(s) to {process_id}"

    async def sessions_yield(message: str) -> str:
        return f"Yielded to parent: {message}"

    async def subagents(action: str = "list") -> str:
        if action != "list":
            return "Mia dynamic sub-agents are tracked in Convex agentSpawns. Supported action here: list."
        return (
            "Mia uses parent_router -> dynamic_sub_agent. "
            "Live spawned agents are visible in the dashboard Agents view and Convex agentSpawns."
        )

    async def nodes(action: str = "status") -> str:
        return await gateway(action="status" if action else "status")

    async def canvas(title: str, content: str = "") -> str:
        MIA_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        safe_title = re.sub(r"[^a-zA-Z0-9_.-]+", "-", title.strip())[:48] or "canvas"
        path = MIA_RUNTIME_DIR / f"{safe_title}.md"
        path.write_text(content)
        return f"Saved canvas note: {path}"

    async def image_generate(prompt: str) -> str:
        return (
            "image_generate is registered, but no image generation provider is configured in Mia. "
            "Add an image provider endpoint before using this tool."
        )

    async def music_generate(prompt: str) -> str:
        return (
            "music_generate is registered, but no music generation provider is configured in Mia. "
            "Add a music provider endpoint before using this tool."
        )

    async def video_generate(prompt: str) -> str:
        return (
            "video_generate is registered, but no video generation provider is configured in Mia. "
            "Add a video provider endpoint before using this tool."
        )

    async def request_click_screen(x: int, y: int, button: str = "left") -> str:
        summary = f"Click screen at x={x} y={y}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="click_screen",
            summary=summary,
            payload={"x": x, "y": y, "button": button},
            risk="approval_required",
        )

    async def request_type_text(text: str) -> str:
        summary = f"Type text into the active app ({len(text)} characters)"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="type_text",
            summary=summary,
            payload={"text": text},
            risk="approval_required",
        )

    async def request_press_key(key: str, modifiers: list[str] | None = None) -> str:
        modifiers = modifiers or []
        summary = f"Press key: {'+'.join([*modifiers, key]) if modifiers else key}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="press_key",
            summary=summary,
            payload={"key": key, "modifiers": modifiers},
            risk="approval_required",
        )

    async def request_scroll(amount: int) -> str:
        summary = f"Scroll active window by {amount}"
        return await _create_pending_action(
            convex,
            requester_number=requester_number,
            message_handle=message_handle,
            run_id=run_id,
            kind="scroll",
            summary=summary,
            payload={"amount": amount},
            risk="approval_required",
        )

    return [
        StructuredTool.from_function(
            coroutine=open_url,
            name="open_url",
            description="Open a safe http or https URL in the user's default browser on this Mac.",
        ),
        StructuredTool.from_function(
            coroutine=get_frontmost_app,
            name="get_frontmost_app",
            description="Return the name of the currently frontmost macOS application.",
        ),
        StructuredTool.from_function(
            coroutine=list_running_apps,
            name="list_running_apps",
            description="List visible running macOS applications.",
        ),
        StructuredTool.from_function(
            coroutine=screenshot_desktop,
            name="screenshot_desktop",
            description="Capture the current Mac desktop to a local PNG and return the saved path.",
        ),
        StructuredTool.from_function(
            coroutine=read_file,
            name="read_file",
            description="Read a local text file. Use only when the user asks to inspect a file.",
        ),
        StructuredTool.from_function(
            coroutine=read_file,
            name="read",
            description="OpenClaw-compatible alias for read_file.",
        ),
        StructuredTool.from_function(
            coroutine=list_directory,
            name="list_directory",
            description="List files and directories at a local path.",
        ),
        StructuredTool.from_function(
            coroutine=file_info,
            name="file_info",
            description="Return local file or directory metadata such as type, size, and timestamps.",
        ),
        StructuredTool.from_function(
            coroutine=search_files,
            name="search_files",
            description="Search local file paths by name under a directory using ripgrep file listing.",
        ),
        StructuredTool.from_function(
            coroutine=fetch_webpage,
            name="fetch_webpage",
            description="Fetch a webpage over HTTP/HTTPS and return the first 12000 characters.",
        ),
        StructuredTool.from_function(
            coroutine=web_fetch,
            name="web_fetch",
            description="OpenClaw-compatible alias for fetching a webpage over HTTP/HTTPS.",
        ),
        StructuredTool.from_function(
            coroutine=get_clipboard,
            name="get_clipboard",
            description="Read the current macOS clipboard text.",
        ),
        StructuredTool.from_function(
            coroutine=image_info,
            name="image_info",
            description="Inspect local image metadata using macOS image tools.",
        ),
        StructuredTool.from_function(
            coroutine=image,
            name="image",
            description="OpenClaw-compatible alias for local image inspection.",
        ),
        StructuredTool.from_function(
            coroutine=extract_pdf_text,
            name="extract_pdf_text",
            description="Extract text from a local PDF file when a PDF text backend is available.",
        ),
        StructuredTool.from_function(
            coroutine=pdf,
            name="pdf",
            description="OpenClaw-compatible alias for extracting text from a local PDF.",
        ),
        StructuredTool.from_function(
            coroutine=process_list,
            name="process_list",
            description="List background processes started by Mia's process_start tool.",
        ),
        StructuredTool.from_function(
            coroutine=process_read,
            name="process_read",
            description="Read the log tail for a background process started by Mia.",
        ),
        StructuredTool.from_function(
            coroutine=process,
            name="process",
            description="OpenClaw-compatible process manager alias.",
        ),
        StructuredTool.from_function(
            coroutine=gateway,
            name="gateway",
            description="Read Mia gateway heartbeat/status information.",
        ),
        StructuredTool.from_function(
            coroutine=sessions_list,
            name="sessions_list",
            description="OpenClaw-compatible alias for listing Mia-managed background sessions.",
        ),
        StructuredTool.from_function(
            coroutine=sessions_history,
            name="sessions_history",
            description="OpenClaw-compatible alias for listing Mia-managed session log history.",
        ),
        StructuredTool.from_function(
            coroutine=sessions_send,
            name="sessions_send",
            description="Send text to a Mia-managed process session when stdin is available.",
        ),
        StructuredTool.from_function(
            coroutine=sessions_yield,
            name="sessions_yield",
            description="Yield a message back to the parent agent.",
        ),
        StructuredTool.from_function(
            coroutine=subagents,
            name="subagents",
            description="OpenClaw-compatible subagent status surface for Mia dynamic sub-agents.",
        ),
        StructuredTool.from_function(
            coroutine=nodes,
            name="nodes",
            description="OpenClaw-compatible node status surface mapped to Mia gateway status.",
        ),
        StructuredTool.from_function(
            coroutine=canvas,
            name="canvas",
            description="Create a lightweight local Markdown canvas note under .mia.",
        ),
        StructuredTool.from_function(
            coroutine=image_generate,
            name="image_generate",
            description="OpenClaw-compatible image generation surface; requires a configured provider.",
        ),
        StructuredTool.from_function(
            coroutine=music_generate,
            name="music_generate",
            description="OpenClaw-compatible music generation surface; requires a configured provider.",
        ),
        StructuredTool.from_function(
            coroutine=video_generate,
            name="video_generate",
            description="OpenClaw-compatible video generation surface; requires a configured provider.",
        ),
        StructuredTool.from_function(
            coroutine=request_terminal_command,
            name="run_terminal_command",
            description="Request approval to run a terminal command on this Mac.",
        ),
        StructuredTool.from_function(
            coroutine=request_exec,
            name="exec",
            description="OpenClaw-compatible alias for run_terminal_command.",
        ),
        StructuredTool.from_function(
            coroutine=request_write_file,
            name="write_file",
            description="Request approval to write a local file.",
        ),
        StructuredTool.from_function(
            coroutine=request_write,
            name="write",
            description="OpenClaw-compatible alias for write_file.",
        ),
        StructuredTool.from_function(
            coroutine=request_delete_file,
            name="delete_file",
            description="Request approval to delete a local file.",
        ),
        StructuredTool.from_function(
            coroutine=request_append_file,
            name="append_file",
            description="Request approval to append text to a local file.",
        ),
        StructuredTool.from_function(
            coroutine=request_replace_in_file,
            name="replace_in_file",
            description="Request approval to replace exact text inside a local text file.",
        ),
        StructuredTool.from_function(
            coroutine=request_edit,
            name="edit",
            description="OpenClaw-compatible alias for exact text replacement in a local file.",
        ),
        StructuredTool.from_function(
            coroutine=request_apply_patch,
            name="apply_patch",
            description="Request approval to apply a local workspace patch.",
        ),
        StructuredTool.from_function(
            coroutine=request_create_directory,
            name="create_directory",
            description="Request approval to create a local directory.",
        ),
        StructuredTool.from_function(
            coroutine=request_copy_file,
            name="copy_file",
            description="Request approval to copy a local file.",
        ),
        StructuredTool.from_function(
            coroutine=request_move_file,
            name="move_file",
            description="Request approval to move or rename a local file.",
        ),
        StructuredTool.from_function(
            coroutine=request_open_app,
            name="open_app",
            description="Request approval to open a local macOS application.",
        ),
        StructuredTool.from_function(
            coroutine=request_set_clipboard,
            name="set_clipboard",
            description="Request approval to replace the macOS clipboard text.",
        ),
        StructuredTool.from_function(
            coroutine=request_show_notification,
            name="show_notification",
            description="Request approval to show a macOS notification.",
        ),
        StructuredTool.from_function(
            coroutine=request_speak_text,
            name="speak_text",
            description="Request approval to speak text aloud with the macOS say command.",
        ),
        StructuredTool.from_function(
            coroutine=request_process_start,
            name="process_start",
            description="Request approval to start a long-running background shell process.",
        ),
        StructuredTool.from_function(
            coroutine=request_sessions_spawn,
            name="sessions_spawn",
            description="OpenClaw-compatible alias to request a managed background shell session.",
        ),
        StructuredTool.from_function(
            coroutine=request_process_kill,
            name="process_kill",
            description="Request approval to terminate a background process started by Mia.",
        ),
        StructuredTool.from_function(
            coroutine=request_send_imessage,
            name="send_imessage",
            description="Request approval to send an outbound iMessage through SendBlue.",
        ),
        StructuredTool.from_function(
            coroutine=request_message,
            name="message",
            description="OpenClaw-compatible alias for sending an outbound iMessage through SendBlue.",
        ),
        StructuredTool.from_function(
            coroutine=request_create_reminder,
            name="create_reminder",
            description="Request approval to create a macOS Reminders reminder.",
        ),
        StructuredTool.from_function(
            coroutine=request_cron,
            name="cron",
            description="OpenClaw-compatible reminder scheduling alias backed by macOS Reminders.",
        ),
        StructuredTool.from_function(
            coroutine=request_tts,
            name="tts",
            description="OpenClaw-compatible text-to-speech alias backed by macOS say.",
        ),
        StructuredTool.from_function(
            coroutine=request_click_screen,
            name="click_screen",
            description="Request approval to click an absolute screen coordinate on this Mac.",
        ),
        StructuredTool.from_function(
            coroutine=request_type_text,
            name="type_text",
            description="Request approval to type text into the active app.",
        ),
        StructuredTool.from_function(
            coroutine=request_press_key,
            name="press_key",
            description="Request approval to press a key with optional modifiers such as command or shift.",
        ),
        StructuredTool.from_function(
            coroutine=request_scroll,
            name="scroll",
            description="Request approval to scroll the active window by a signed amount.",
        ),
    ]


def execute_pending_action(action: dict[str, Any]) -> str:
    kind = action["kind"]
    payload = action["payload"]
    if kind == "run_terminal_command":
        cwd = payload.get("cwd") or None
        completed = subprocess.run(
            payload["command"],
            cwd=cwd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=120,
        )
        output = "\n".join(
            part for part in [completed.stdout.strip(), completed.stderr.strip()] if part
        )
        return f"exit={completed.returncode}\n{output}"[:12000]
    if kind == "write_file":
        path = Path(payload["path"]).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload["content"])
        return f"Wrote {path}"
    if kind == "append_file":
        path = Path(payload["path"]).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as handle:
            handle.write(payload["content"])
        return f"Appended to {path}"
    if kind == "replace_in_file":
        path = Path(payload["path"]).expanduser().resolve()
        if not path.exists() or not path.is_file():
            return f"File not found: {path}"
        old = str(payload["old"])
        new = str(payload["new"])
        content = path.read_text(errors="replace")
        if old not in content:
            return f"Text not found in {path}"
        path.write_text(content.replace(old, new, 1))
        return f"Replaced text in {path}"
    if kind == "delete_file":
        path = Path(payload["path"]).expanduser().resolve()
        if path.exists() and path.is_file():
            path.unlink()
            return f"Deleted {path}"
        return f"File not found: {path}"
    if kind == "create_directory":
        path = Path(payload["path"]).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return f"Created directory {path}"
    if kind == "copy_file":
        source = Path(payload["source"]).expanduser().resolve()
        destination = Path(payload["destination"]).expanduser().resolve()
        if not source.exists() or not source.is_file():
            return f"File not found: {source}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return f"Copied {source} to {destination}"
    if kind == "move_file":
        source = Path(payload["source"]).expanduser().resolve()
        destination = Path(payload["destination"]).expanduser().resolve()
        if not source.exists():
            return f"Path not found: {source}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        return f"Moved {source} to {destination}"
    if kind == "open_app":
        subprocess.run(["open", "-a", payload["app_name"]], check=True)
        return f"Opened {payload['app_name']}"
    if kind == "set_clipboard":
        return _execute_set_clipboard(str(payload["text"]))
    if kind == "show_notification":
        return _execute_show_notification(str(payload["title"]), str(payload["message"]))
    if kind == "speak_text":
        return _execute_speak_text(str(payload["text"]), str(payload.get("voice") or ""))
    if kind == "process_start":
        return _execute_process_start(str(payload["command"]), str(payload.get("cwd") or ""))
    if kind == "process_kill":
        return _execute_process_kill(str(payload["process_id"]))
    if kind == "send_imessage":
        api_key_id = os.environ.get("SENDBLUE_API_KEY_ID", "")
        api_secret = os.environ.get("SENDBLUE_API_SECRET_KEY", "")
        from_number = os.environ.get("SENDBLUE_FROM_NUMBER", "")
        if not api_key_id or not api_secret or not from_number:
            return "SendBlue credentials are missing."
        with httpx.Client(timeout=30) as client:
            response = client.post(
                "https://api.sendblue.co/api/send-message",
                headers={
                    "Content-Type": "application/json",
                    "sb-api-key-id": api_key_id,
                    "sb-api-secret-key": api_secret,
                },
                json={
                    "content": str(payload["content"]),
                    "from_number": from_number,
                    "number": str(payload["number"]),
                },
            )
            response.raise_for_status()
        return f"Sent iMessage to {payload['number']}"
    if kind == "create_reminder":
        title = str(payload["title"]).replace("\\", "\\\\").replace('"', '\\"')
        remind_at = str(payload.get("remind_at") or "").replace("\\", "\\\\").replace('"', '\\"')
        if remind_at:
            script = (
                'tell application "Reminders" to make new reminder '
                f'with properties {{name:"{title}", remind me date:date "{remind_at}"}}'
            )
        else:
            script = f'tell application "Reminders" to make new reminder with properties {{name:"{title}"}}'
        _run_osascript(script)
        return f"Created reminder: {payload['title']}"
    if kind == "click_screen":
        return _execute_click_screen(
            int(payload["x"]),
            int(payload["y"]),
            str(payload.get("button") or "left"),
        )
    if kind == "type_text":
        return _execute_type_text(str(payload["text"]))
    if kind == "press_key":
        modifiers = payload.get("modifiers")
        if not isinstance(modifiers, list):
            modifiers = []
        return _execute_press_key(str(payload["key"]), [str(modifier) for modifier in modifiers])
    if kind == "scroll":
        return _execute_scroll(int(payload["amount"]))
    raise ValueError(f"Unsupported pending action kind: {kind}")
