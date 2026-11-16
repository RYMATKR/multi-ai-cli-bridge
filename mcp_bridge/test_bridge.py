#!/usr/bin/env python3
"""Smoke test for mcp_bridge/server.py over stdio JSON-RPC."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    server_path = Path(__file__).resolve().parent / "server.py"
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.1.0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "check_ai_agents", "arguments": {}},
        },
    ]

    stdin_payload = "\n".join(json.dumps(r) for r in requests) + "\n"
    proc = subprocess.run(
        [sys.executable, str(server_path)],
        input=stdin_payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    if proc.returncode != 0:
        print(f"Server exited with {proc.returncode}")
        print(proc.stderr)
        return 1

    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if len(lines) != 3:
        print(f"Expected 3 JSON-RPC responses, got {len(lines)}")
        print("STDOUT:", proc.stdout)
        print("STDERR:", proc.stderr)
        return 1

    responses = [json.loads(line) for line in lines]

    init_res = responses[0]["result"]
    assert init_res["serverInfo"]["name"] == "multi-ai-cli-bridge"

    tools = [t["name"] for t in responses[1]["result"]["tools"]]
    assert tools == [
        "check_ai_agents",
        "list_models",
        "check_usage",
        "get_repo_summary",
        "ask_claude",
        "ask_codex",
        "ask_gemini",
    ], tools

    agent_status = json.loads(responses[2]["result"]["content"][0]["text"])
    print("MCP Bridge Smoke Test PASSED!")
    print("Detected AI CLIs:")
    print(json.dumps(agent_status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
