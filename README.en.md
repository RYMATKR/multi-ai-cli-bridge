# Multi-AI CLI Bridge & Orchestrator

English | [日本語](README.md)

A lightweight **MCP (Model Context Protocol) server** and shared **Agent Skill (`SKILL.md`)** that lets **Claude Code**, **OpenAI Codex CLI**, and **Antigravity (`agy`) / Gemini CLI** collaborate using your **existing local subscription sessions (OAuth)**—without requiring separate pay-per-token API keys.

---

## Features

* **Zero External Dependencies**: Built solely on the Python 3.10+ standard library (`pip install` not required).
* **Subscription-First (`use_subscription_only: true`)**: Strips API key environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`) by default so local OAuth sessions are used.
* **Role Delegation & Write Control (`read_only`)**: Keep `read_only: true` for investigation/review, or set `read_only: false` to delegate file edits (`workspace-write` for Codex, `--mode auto --dangerously-skip-permissions` for `agy`).
* **Quota Tracking (`check_usage`)**: Fetches remaining 5-hour/weekly quotas from `agy -p "/usage"` and local Codex session logs (`~/.codex/sessions/`), and appends `[Quota Remaining]` after tool calls.
* **Model Discovery & Validation (`list_models`)**: Lists available models across CLIs and pre-validates Codex model slugs against `~/.codex/models_cache.json`.
* **Windows-Friendly**: Passes prompts to Codex via `stdin` (`codex exec -`) to avoid Windows `.cmd` newline truncation, and enforces UTF-8 environment variables.

---

## Available MCP Tools

| Tool | Description |
| :--- | :--- |
| `check_ai_agents` | Check installation status and versions of `claude`, `codex`, `agy`, and `gemini` |
| `list_models` | List available models and configured defaults for each CLI |
| `check_usage` | Check remaining quota percentages and reset times for `agy` and `codex` |
| `ask_claude` | Invoke Claude Code CLI in non-interactive mode (`claude -p`) |
| `ask_codex` | Invoke OpenAI Codex CLI in non-interactive mode (`codex exec -`) |
| `ask_gemini` | Invoke Antigravity CLI (`agy`) or Gemini CLI (`gemini`) |

---

## Compatibility

* **Verified**: Windows 11 + Python 3.11
* **macOS / Linux**: Designed to work on Python 3.10+, but not yet tested on these platforms.
* **Prerequisites**: Install the target CLIs beforehand and complete interactive OAuth login once for each CLI you plan to use.

---

## Setup (Windows)

### 1. Clone & Install

```powershell
git clone https://github.com/RYMATKR/multi-ai-cli-bridge.git multi-ai-cli-bridge
cd multi-ai-cli-bridge
.\install.ps1
```

`install.ps1` copies:
1. `server.py` and `test_bridge.py` to `~/.local/share/multi-ai-bridge/`
2. The `multi-ai-orchestrator` skill to `~/.claude/skills/` and `~/.gemini/config/skills/`
3. Runs `test_bridge.py` to verify installation

### 2. Register in Your AI Client

#### Claude Code
```powershell
claude mcp add -s user --transport stdio multi-ai-bridge -- python "$env:USERPROFILE/.local/share/multi-ai-bridge/server.py"
```
Or copy [configs/claude.mcp.json](configs/claude.mcp.json) as `.mcp.json` in your project root (replace `<USER_HOME>` with your home path).

#### Antigravity
Add the entry from [configs/antigravity.mcp_config.json](configs/antigravity.mcp_config.json) to `~/.gemini/config/mcp_config.json` (replace `<USER_HOME>` with your home path).

---

## Security & Disclaimers

* **File Edit Permissions**: When `read_only: false` is passed, `codex` runs with `--sandbox workspace-write` and `agy` runs with `--mode auto --dangerously-skip-permissions`. **Always work inside a Git-tracked repository and review diffs.**
* **Secrets Handling**: Never pass `.env`, API keys, tokens, or production deployment scripts to sub-agents.
* **Terms of Service**: This tool is a local wrapper around official CLIs. Use it strictly within the terms and rate limits of your respective subscriptions.

---

## License

[MIT License](LICENSE)

---

## Credits

This repository (the MCP bridge, orchestration skills, and documentation) was built with **Gemini 4 Hydrogen**.
