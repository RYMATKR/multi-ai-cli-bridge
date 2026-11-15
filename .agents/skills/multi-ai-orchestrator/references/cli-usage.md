# CLI Direct Usage Reference (Fallback)

MCPサーバー（`multi-ai-cli-bridge`）が未登録の環境や、手動で各CLIを確認したい場合のリファレンスです。

## 1. インストールコマンド（Windows）

* **Claude Code**: 公式インストーラーで導入済み想定（`claude --version` で確認）
* **OpenAI Codex CLI**:
  ```powershell
  npm install -g @openai/codex
  codex login
  ```
* **Antigravity CLI (`agy`)**:
  ```powershell
  irm https://antigravity.google/cli/install.ps1 | iex
  agy
  ```
* **Gemini CLI（代替）**:
  ```powershell
  npm install -g @google/gemini-cli
  gemini
  ```

## 2. 非対話モードでの呼び出し方

* **Claude Code**:
  ```powershell
  claude -p "ここに指示" --tools Read,Grep,Glob
  ```
* **Codex CLI**:
  ```powershell
  codex exec --sandbox read-only "ここに指示"
  ```
* **Antigravity CLI / Gemini CLI**:
  ```powershell
  agy -p "ここに指示"
  # または
  gemini -p "ここに指示"
  ```
