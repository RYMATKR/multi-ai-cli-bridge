#!/usr/bin/env python3
"""Lightweight MCP (Model Context Protocol) stdio bridge for local AI CLIs.

Exposes Claude Code (`claude`), OpenAI Codex (`codex`), and Antigravity/Gemini
(`agy` / `gemini`) as MCP tools using local OAuth/subscription sessions without
requiring external dependencies.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SERVER_NAME = "multi-ai-cli-bridge"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"
DEFAULT_TIMEOUT_SEC = 180

# API key env vars that override subscription OAuth sessions if present.
API_KEY_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
)


def _log(msg: str) -> None:
    """Write diagnostic logs to stderr so stdout stays strictly JSON-RPC."""
    sys.stderr.write(f"[{SERVER_NAME}] {msg}\n")
    sys.stderr.flush()


def _find_cli_executable(name: str) -> str | None:
    """Locate a CLI executable via PATH or common Windows install locations."""
    found = shutil.which(name)
    if found:
        return found

    if os.name == "nt":
        home = Path.home()
        candidates: dict[str, list[Path]] = {
            "claude": [
                home / ".local" / "bin" / "claude.exe",
            ],
            "agy": [
                home / "AppData" / "Local" / "agy" / "bin" / "agy.exe",
            ],
            "codex": [
                home / "AppData" / "Roaming" / "npm" / "codex.cmd",
                home / "AppData" / "Roaming" / "npm" / "codex.exe",
            ],
            "gemini": [
                home / "AppData" / "Roaming" / "npm" / "gemini.cmd",
                home / "AppData" / "Roaming" / "npm" / "gemini.exe",
            ],
        }
        for candidate in candidates.get(name, []):
            if candidate.is_file():
                return str(candidate)

    return None


def _build_subprocess_env(use_subscription_only: bool) -> dict[str, str]:
    """Build environment variables for child CLI processes."""
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["LANG"] = "C.UTF-8"
    env["LC_ALL"] = "C.UTF-8"
    env["NO_COLOR"] = "1"
    if use_subscription_only:
        for key in API_KEY_ENV_VARS:
            env.pop(key, None)
    return env


def _run_cli(
    cmd: list[str],
    cwd: str | None,
    timeout_sec: int,
    use_subscription_only: bool,
    stdin_text: str | None = None,
) -> dict[str, Any]:
    """Execute a CLI command in non-interactive mode and capture output."""
    work_dir = cwd if cwd and Path(cwd).is_dir() else os.getcwd()
    env = _build_subprocess_env(use_subscription_only)

    try:
        run_kwargs: dict[str, Any] = {
            "cwd": work_dir,
            "env": env,
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": timeout_sec,
        }
        if stdin_text is None:
            run_kwargs["stdin"] = subprocess.DEVNULL
        else:
            run_kwargs["input"] = stdin_text

        proc = subprocess.run(cmd, **run_kwargs)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "command": cmd[0],
            "cwd": work_dir,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": f"Command timed out after {timeout_sec}s.",
            "command": cmd[0],
            "cwd": work_dir,
        }
    except OSError as exc:
        return {
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Failed to execute {cmd[0]}: {exc}",
            "command": cmd[0],
            "cwd": work_dir,
        }


MAX_OUTPUT_CHARS = 30000


def _truncate_text(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    """Truncate overly long text so MCP tool responses stay within safe limits."""
    if len(text) <= limit:
        return text
    head = limit // 2
    tail = limit - head
    omitted = len(text) - limit
    return f"{text[:head]}\n\n... [truncated {omitted:,} chars] ...\n\n{text[-tail:]}"


def _format_cli_result(agent_label: str, result: dict[str, Any]) -> tuple[str, bool]:
    """Format CLI execution output as readable text for the orchestrating agent."""
    if result["ok"]:
        # Do not append stderr on success: Codex streams full command/file traces
        # and startup warnings to stderr, while stdout holds the final message.
        output = result["stdout"] or "(No stdout returned)"
        return _truncate_text(output), False

    lines = [
        f"{agent_label} execution failed (exit code: {result['returncode']}).",
        f"Command: {result['command']}",
        f"Working Directory: {result['cwd']}",
    ]
    if result["stdout"]:
        lines.append(f"\n[stdout]\n{_truncate_text(result['stdout'], 8000)}")
    if result["stderr"]:
        lines.append(f"\n[stderr]\n{_truncate_text(result['stderr'], 8000)}")
    return "\n".join(lines), True


def handle_check_ai_agents(_args: dict[str, Any]) -> tuple[str, bool]:
    """Check installation status of claude, codex, agy, and gemini CLIs."""
    status: dict[str, Any] = {}
    for name in ("claude", "codex", "agy", "gemini"):
        exe = _find_cli_executable(name)
        if not exe:
            status[name] = {"installed": False, "path": None, "version": None}
            continue

        ver_res = _run_cli([exe, "--version"], cwd=None, timeout_sec=10, use_subscription_only=True)
        ver_text = ver_res["stdout"] or ver_res["stderr"] or "unknown"
        status[name] = {
            "installed": True,
            "path": exe,
            "version": ver_text.splitlines()[0] if ver_text else "unknown",
        }

    return json.dumps(status, ensure_ascii=False, indent=2), False


def handle_ask_claude(args: dict[str, Any]) -> tuple[str, bool]:
    """Invoke Claude Code CLI in non-interactive print mode."""
    exe = _find_cli_executable("claude")
    if not exe:
        return "Claude Code CLI (`claude`) was not found on PATH.", True

    prompt = str(args.get("prompt", "")).strip()
    if not prompt:
        return "Parameter `prompt` is required.", True

    cwd = args.get("cwd")
    read_only = bool(args.get("read_only", True))
    model = str(args.get("model", "")).strip()
    timeout_sec = int(args.get("timeout_sec", DEFAULT_TIMEOUT_SEC))
    use_sub = bool(args.get("use_subscription_only", True))

    cmd = [exe, "-p", prompt]
    if model:
        cmd.extend(["--model", model])
    if read_only:
        # Restrict tools when used purely for consultation/review.
        cmd.extend(["--tools", "Read,Grep,Glob"])

    result = _run_cli(cmd, cwd=cwd, timeout_sec=timeout_sec, use_subscription_only=use_sub)
    return _format_cli_result("Claude Code", result)


def _format_local_time(ts_or_iso: Any) -> str:
    """Convert a Unix timestamp or ISO-8601 string into local readable time."""
    try:
        if isinstance(ts_or_iso, (int, float)):
            dt = datetime.fromtimestamp(float(ts_or_iso), tz=timezone.utc).astimezone()
            return dt.strftime("%Y-%m-%d %H:%M")
        if isinstance(ts_or_iso, str) and ts_or_iso:
            dt = datetime.fromisoformat(ts_or_iso.replace("Z", "+00:00")).astimezone()
            return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError, OverflowError):
        pass
    return str(ts_or_iso or "unknown")


def _get_agy_usage_summary() -> str:
    """Query Antigravity CLI (`/usage`) without consuming model tokens."""
    exe = _find_cli_executable("agy")
    if not exe:
        return "Antigravity (`agy`): not installed"

    res = _run_cli([exe, "-p", "/usage", "--output-format", "json"], cwd=None, timeout_sec=20, use_subscription_only=True)
    if not res["ok"]:
        return f"Antigravity (`agy`): failed to fetch usage ({res['stderr'] or res['returncode']})"

    try:
        data = json.loads(res["stdout"])
        groups = data.get("command", {}).get("data", {}).get("groups", [])
        if not groups:
            return "Antigravity (`agy`): no quota buckets returned"
        lines = ["Antigravity (`agy`) Quota Remaining:"]
        for grp in groups:
            gname = grp.get("name", "Unknown")
            for b in grp.get("buckets", []):
                bname = b.get("name", b.get("id", "limit"))
                frac = b.get("remaining_fraction")
                pct = f"{frac * 100:.1f}%" if isinstance(frac, (int, float)) else "N/A"
                reset = _format_local_time(b.get("reset_time"))
                lines.append(f"  - {gname} / {bname}: {pct} (resets {reset})")
        return "\n".join(lines)
    except (json.JSONDecodeError, TypeError, AttributeError) as exc:
        return f"Antigravity (`agy`): failed to parse usage JSON ({exc})"


def _get_codex_usage_summary() -> str:
    """Read latest Codex CLI local session JSONL for rate_limits and token usage."""
    sessions_dir = Path.home() / ".codex" / "sessions"
    if not sessions_dir.is_dir():
        return "Codex: no local session logs found yet"

    files = list(sessions_dir.rglob("*.jsonl"))
    if not files:
        return "Codex: no local session logs found yet"

    latest = max(files, key=lambda p: p.stat().st_mtime)
    last_payload: dict[str, Any] | None = None
    try:
        with latest.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"token_count"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                    payload = obj.get("payload")
                    if isinstance(payload, dict) and payload.get("type") == "token_count":
                        last_payload = payload
                except json.JSONDecodeError:
                    continue
    except OSError as exc:
        return f"Codex: failed to read session log ({exc})"

    if not last_payload:
        return "Codex: no token_count entry found in latest session"

    rl = last_payload.get("rate_limits") or {}
    plan = rl.get("plan_type") or "unknown"
    lines = [f"Codex (plan: {plan}) Quota Remaining:"]

    for label, key in (("Primary", "primary"), ("Secondary", "secondary")):
        bucket = rl.get(key)
        if not isinstance(bucket, dict):
            continue
        used = bucket.get("used_percent")
        rem_pct = f"{max(0.0, 100.0 - float(used)):.1f}%" if isinstance(used, (int, float)) else "N/A"
        win_min = bucket.get("window_minutes")
        win_str = f"{int(win_min) // 60}h" if isinstance(win_min, (int, float)) else "unknown"
        reset = _format_local_time(bucket.get("resets_at"))
        lines.append(f"  - {label} ({win_str} window): {rem_pct} remaining (resets {reset})")

    total_tok = (last_payload.get("info") or {}).get("total_token_usage", {}).get("total_tokens")
    if total_tok is not None:
        lines.append(f"  - Last session tokens used: {total_tok:,}")

    return "\n".join(lines)


def _get_codex_available_models() -> list[dict[str, str]]:
    """Read visible Codex models from local ~/.codex/models_cache.json."""
    cache_path = Path.home() / ".codex" / "models_cache.json"
    if not cache_path.is_file():
        return []
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8", errors="replace"))
        models = []
        for item in data.get("models", []):
            if item.get("visibility") == "list" and item.get("slug"):
                models.append(
                    {
                        "id": str(item["slug"]),
                        "display_name": str(item.get("display_name") or item["slug"]),
                    }
                )
        return models
    except (OSError, json.JSONDecodeError, TypeError):
        return []


def _get_agy_available_models() -> tuple[list[dict[str, str]], str | None]:
    """Fetch available Antigravity models via `agy models` and read configured default."""
    configured_model: str | None = None
    settings_path = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"
    if settings_path.is_file():
        try:
            cfg = json.loads(settings_path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(cfg.get("model"), str):
                configured_model = cfg["model"]
        except (OSError, json.JSONDecodeError):
            pass

    exe = _find_cli_executable("agy")
    if not exe:
        return [], configured_model

    res = _run_cli([exe, "models"], cwd=None, timeout_sec=20, use_subscription_only=True)
    if not res["ok"]:
        return [], configured_model

    models: list[dict[str, str]] = []
    for line in res["stdout"].splitlines():
        line = line.strip()
        if not line or line.startswith("Fetching "):
            continue
        parts = line.split("\t", 1)
        model_id = parts[0].strip()
        display = parts[1].strip() if len(parts) > 1 else model_id
        models.append({"id": model_id, "display_name": display})
    return models, configured_model


def handle_list_models(_args: dict[str, Any]) -> tuple[str, bool]:
    """List available models for Antigravity (`agy`), Codex, and Claude Code."""
    lines: list[str] = []

    agy_models, agy_default = _get_agy_available_models()
    lines.append(f"Antigravity (`agy`) [configured default: {agy_default or 'auto'}]:")
    if agy_models:
        for m in agy_models:
            lines.append(f"  - {m['id']} ({m['display_name']})")
    else:
        lines.append("  - (unavailable or not installed)")

    codex_models = _get_codex_available_models()
    lines.append("\nCodex (`codex`) [from ~/.codex/models_cache.json]:")
    if codex_models:
        for m in codex_models:
            lines.append(f"  - {m['id']} ({m['display_name']})")
    else:
        lines.append("  - (no cached models found; default plan model will be used)")

    claude_default = "auto"
    claude_settings = Path.home() / ".claude" / "settings.json"
    if claude_settings.is_file():
        try:
            c_cfg = json.loads(claude_settings.read_text(encoding="utf-8", errors="replace"))
            if isinstance(c_cfg.get("model"), str):
                claude_default = c_cfg["model"]
        except (OSError, json.JSONDecodeError):
            pass
    lines.append(f"\nClaude Code (`claude`) [configured default: {claude_default}]:")
    lines.append("  - Aliases: default, sonnet, opus, haiku")

    return "\n".join(lines), False


def handle_check_usage(_args: dict[str, Any]) -> tuple[str, bool]:
    """Return remaining subscription quota summaries for Antigravity and Codex."""
    sections = [_get_agy_usage_summary(), _get_codex_usage_summary()]
    return "\n\n".join(sections), False


def handle_ask_codex(args: dict[str, Any]) -> tuple[str, bool]:
    """Invoke OpenAI Codex CLI in non-interactive `exec` mode."""
    exe = _find_cli_executable("codex")
    if not exe:
        return (
            "Codex CLI (`codex`) was not found. Install it with: npm install -g @openai/codex",
            True,
        )

    prompt = str(args.get("prompt", "")).strip()
    if not prompt:
        return "Parameter `prompt` is required.", True

    cwd = args.get("cwd")
    read_only = bool(args.get("read_only", True))
    model = str(args.get("model", "")).strip()
    timeout_sec = int(args.get("timeout_sec", DEFAULT_TIMEOUT_SEC))
    use_sub = bool(args.get("use_subscription_only", True))
    show_usage = bool(args.get("show_usage", True))

    if model:
        available = _get_codex_available_models()
        valid_ids = [m["id"] for m in available]
        if valid_ids and model not in valid_ids:
            return (
                f"Model `{model}` is not available for your current Codex plan. "
                f"Available models: {', '.join(valid_ids)}",
                True,
            )

    sandbox_mode = "read-only" if read_only else "workspace-write"
    # Pass prompt via stdin ('-') to avoid Windows .cmd newline truncation and length limits.
    cmd = [exe, "exec", "--sandbox", sandbox_mode, "--skip-git-repo-check"]
    if model:
        cmd.extend(["--model", model])
    cmd.append("-")
    utf8_prefix = (
        "[Windows UTF-8 Rule: Always read and write files with explicit UTF-8 encoding "
        "(e.g. Get-Content -Encoding utf8 or Python encoding='utf-8').]\n\n"
    )
    full_prompt = prompt if "UTF-8" in prompt.upper() else utf8_prefix + prompt

    result = _run_cli(
        cmd,
        cwd=cwd,
        timeout_sec=timeout_sec,
        use_subscription_only=use_sub,
        stdin_text=full_prompt,
    )
    text, is_err = _format_cli_result("Codex CLI", result)
    if show_usage and not is_err:
        text += f"\n\n[Quota Remaining]\n{_get_codex_usage_summary()}"
    return text, is_err


def handle_ask_gemini(args: dict[str, Any]) -> tuple[str, bool]:
    """Invoke Antigravity CLI (`agy`) or Gemini CLI (`gemini`) in non-interactive mode."""
    backend = str(args.get("backend", "auto")).lower()
    exe: str | None = None
    selected_backend = backend

    if backend == "auto":
        exe = _find_cli_executable("agy")
        if exe:
            selected_backend = "agy"
        else:
            exe = _find_cli_executable("gemini")
            selected_backend = "gemini"
    elif backend in ("agy", "gemini"):
        exe = _find_cli_executable(backend)
    else:
        return f"Invalid backend `{backend}`. Choose from: auto, agy, gemini.", True

    if not exe:
        return (
            "Neither Antigravity CLI (`agy`) nor Gemini CLI (`gemini`) was found. "
            "Install `agy` or run `npm install -g @google/gemini-cli`.",
            True,
        )

    prompt = str(args.get("prompt", "")).strip()
    if not prompt:
        return "Parameter `prompt` is required.", True

    cwd = args.get("cwd")
    read_only = bool(args.get("read_only", True))
    model = str(args.get("model", "")).strip()
    timeout_sec = int(args.get("timeout_sec", DEFAULT_TIMEOUT_SEC))
    use_sub = bool(args.get("use_subscription_only", True))
    show_usage = bool(args.get("show_usage", True))

    if selected_backend == "agy":
        if read_only:
            cmd = [exe, "--mode", "plan"]
        else:
            # Use 'auto' mode and skip permission prompts so non-interactive edits do not stall waiting for approval.
            cmd = [exe, "--mode", "auto", "--dangerously-skip-permissions"]
        if model:
            cmd.extend(["--model", model])
        cmd.extend(["-p", prompt])
    else:
        cmd = [exe]
        if model:
            cmd.extend(["--model", model])
        cmd.extend(["-p", prompt])
    result = _run_cli(cmd, cwd=cwd, timeout_sec=timeout_sec, use_subscription_only=use_sub)
    text, is_err = _format_cli_result(f"Gemini ({selected_backend})", result)
    if show_usage and not is_err and selected_backend == "agy":
        text += f"\n\n[Quota Remaining]\n{_get_agy_usage_summary()}"
    return text, is_err


TOOLS: list[dict[str, Any]] = [
    {
        "name": "check_ai_agents",
        "description": (
            "Check which local AI CLIs (claude, codex, agy, gemini) are installed "
            "and available in the current environment."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "list_models",
        "description": (
            "List available models and configured defaults for Antigravity (`agy`), "
            "Codex (`codex`), and Claude Code (`claude`) under the current plan."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "check_usage",
        "description": (
            "Check remaining subscription quota for Antigravity (`agy`) and latest "
            "Codex CLI rate limits without consuming model tokens."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "ask_claude",
        "description": (
            "Delegate a design, architecture review, or coding task to local Claude Code CLI "
            "using the signed-in subscription session."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Instruction or question for Claude Code.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Optional working directory path.",
                },
                "read_only": {
                    "type": "boolean",
                    "description": "If true (default), restrict Claude to read-only inspection.",
                    "default": True,
                },
                "model": {
                    "type": "string",
                    "description": "Optional model name or alias (run `list_models` to check).",
                },
                "timeout_sec": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 180).",
                    "default": 180,
                },
                "use_subscription_only": {
                    "type": "boolean",
                    "description": "Strip API key env vars so OAuth subscription is used (default: true).",
                    "default": True,
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "ask_codex",
        "description": (
            "Delegate implementation, unit test generation, or code review to local OpenAI Codex CLI "
            "using the signed-in subscription session."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Instruction or coding task for Codex.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Optional working directory path.",
                },
                "read_only": {
                    "type": "boolean",
                    "description": "If true (default), run Codex in read-only sandbox.",
                    "default": True,
                },
                "model": {
                    "type": "string",
                    "description": "Optional Codex model slug (run `list_models` to see valid slugs).",
                },
                "timeout_sec": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 180).",
                    "default": 180,
                },
                "use_subscription_only": {
                    "type": "boolean",
                    "description": "Strip API key env vars so OAuth subscription is used (default: true).",
                    "default": True,
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "ask_gemini",
        "description": (
            "Delegate repository-wide analysis, documentation lookup, or design review to local "
            "Antigravity CLI (`agy`) or Gemini CLI (`gemini`) using the signed-in subscription."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Instruction or analysis task for Gemini/Antigravity.",
                },
                "backend": {
                    "type": "string",
                    "enum": ["auto", "agy", "gemini"],
                    "description": "CLI backend to invoke (default: auto).",
                    "default": "auto",
                },
                "cwd": {
                    "type": "string",
                    "description": "Optional working directory path.",
                },
                "read_only": {
                    "type": "boolean",
                    "description": "If true (default), run agy in plan mode; if false, run in auto mode with auto-approved edits.",
                    "default": True,
                },
                "model": {
                    "type": "string",
                    "description": "Optional model ID (run `list_models` to see valid IDs).",
                },
                "timeout_sec": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 180).",
                    "default": 180,
                },
                "use_subscription_only": {
                    "type": "boolean",
                    "description": "Strip API key env vars so OAuth subscription is used (default: true).",
                    "default": True,
                },
            },
            "required": ["prompt"],
        },
    },
]

TOOL_HANDLERS = {
    "check_ai_agents": handle_check_ai_agents,
    "list_models": handle_list_models,
    "check_usage": handle_check_usage,
    "ask_claude": handle_ask_claude,
    "ask_codex": handle_ask_codex,
    "ask_gemini": handle_ask_gemini,
}


def _send_response(payload: dict[str, Any]) -> None:
    """Write a single JSON-RPC message line to stdout."""
    line = json.dumps(payload, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _handle_request(msg: dict[str, Any]) -> None:
    """Process one incoming JSON-RPC 2.0 request."""
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}

    # Notifications have no 'id' and must not receive a response.
    if req_id is None:
        return

    if method == "initialize":
        client_proto = params.get("protocolVersion") or DEFAULT_PROTOCOL_VERSION
        _send_response(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": client_proto,
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": SERVER_VERSION,
                    },
                },
            }
        )
        return

    if method == "ping":
        _send_response({"jsonrpc": "2.0", "id": req_id, "result": {}})
        return

    if method == "tools/list":
        _send_response({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})
        return

    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments") or {}
        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            _send_response(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                }
            )
            return

        text, is_error = handler(tool_args)
        _send_response(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": text}],
                    "isError": is_error,
                },
            }
        )
        return

    _send_response(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    )


def main() -> None:
    """Main stdio loop reading newline-delimited JSON-RPC requests."""
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    _log("Starting stdio MCP server...")
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            _log(f"Invalid JSON received: {exc}")
            continue

        if isinstance(msg, dict):
            _handle_request(msg)


if __name__ == "__main__":
    main()
