# Multi-AI CLI Bridge & Orchestrator

[English](README.en.md) | 日本語

**Claude Code**・**OpenAI Codex CLI**・**Antigravity (`agy`) / Gemini CLI** の3つのAIエージェントを、**API従量課金ではなく既存のサブスクリプション枠（OAuthログイン済みCLI）のまま連携**させ、1つの依頼から設計・実装・レビューを分担して進めるための軽量 MCP（Model Context Protocol）サーバー ＆ 共通スキル集です。

---

## 主な特徴

* **外部依存ゼロ（Python標準ライブラリのみ）**: `pip install` や仮想環境なしで Python 3.10+ があれば即動作します。
* **サブスク枠（OAuth）優先**: デフォルト（`use_subscription_only: true`）で `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` 等の環境変数をサブプロセスから除外し、ログイン済みのローカルCLIセッションを使用します。
* **役割分担 ＆ 書き込み制御（`read_only`）**: 調査・レビュー時は `read_only: true`、実装を任せるときは `read_only: false`（`agy` は自動承認モード、`codex` は `workspace-write`）を切り替えられます。
* **残量確認（`check_usage`）＆ 自動表示**: `agy -p "/usage"` と Codex のローカルセッションログ（`~/.codex/sessions/`）から残り利用枠を取得し、実行結果の末尾にも自動で表示します。
* **利用可能モデル確認 ＆ 事前検証（`list_models`）**: プランで利用可能なモデル一覧を確認でき、Codex では非対応モデル指定時に実行前エラーで即座に通知します。
* **Windows 対応**: `.cmd` ラッパーによる改行切り捨てを防ぐため `codex` には `stdin` パイプ経由でプロンプトを渡し、UTF-8 環境変数・指示を適用します。

---

## 提供ツール（MCP）

| ツール名 | 役割 |
| :--- | :--- |
| `check_ai_agents` | `claude`, `codex`, `agy`, `gemini` のインストール状態とバージョンを確認 |
| `list_models` | 各CLIで利用可能なモデル一覧と現在のデフォルト設定を確認 |
| `check_usage` | Antigravity (`agy`) と Codex の残り利用枠（`%`・リセット時刻）を確認 |
| `get_repo_summary` | 不要ディレクトリを除外した軽量リポジトリ要約キャッシュを生成・取得 |
| `ask_claude` | Claude Code CLI を非対話モード（`claude -p`）で呼び出し |
| `ask_codex` | OpenAI Codex CLI を非対話モード（`codex exec -`）で呼び出し |
| `ask_gemini` | Antigravity CLI (`agy`) または Gemini CLI (`gemini`) を呼び出し |

---

## 動作環境

* **動作確認済み**: Windows 11 + Python 3.11
* **macOS / Linux**: Python 3.10+ 環境で動作する設計ですが、現時点では実機未検証です。
* **前提条件**: 連携させたい各CLIを事前にインストールし、対話モードで OAuth ログインを完了させておく必要があります。

---

## セットアップ（Windows）

### 1. クローン ＆ インストール

```powershell
git clone https://github.com/RYMATKR/multi-ai-cli-bridge.git multi-ai-cli-bridge
cd multi-ai-cli-bridge
.\install.ps1
```

`install.ps1` は以下を自動で行います：
1. `~/.local/share/multi-ai-bridge/` へ `server.py` と `test_bridge.py` を配置
2. `~/.claude/skills/multi-ai-orchestrator/` および `~/.gemini/config/skills/multi-ai-orchestrator/` へ共通スキルを配置
3. スモークテスト（`test_bridge.py`）の実行

### 2. 各ツールへの MCP 登録

#### Claude Code に登録する場合
```powershell
claude mcp add -s user --transport stdio multi-ai-bridge -- python "$env:USERPROFILE/.local/share/multi-ai-bridge/server.py"
```
または対象プロジェクト直下に [configs/claude.mcp.json](configs/claude.mcp.json) を `.mcp.json` として配置してください（`<USER_HOME>` を環境に合わせて書き換えてください）。

#### Antigravity に登録する場合
`~/.gemini/config/mcp_config.json` に [configs/antigravity.mcp_config.json](configs/antigravity.mcp_config.json) の内容を追記してください（`<USER_HOME>` を環境に合わせて書き換えてください）。

---

## セキュリティ・利用規約上の注意

* **Google Antigravity (`agy`) の利用規約について（重要）**:
  * Google Antigravity 追加利用規約では、**Google が提供していないサードパーティ製ツールと組み合わせて Antigravity（OAuth サブスク認証）へアクセスする行為が禁止されており、アカウント停止（Antigravity / Gemini CLI）の対象になり得る**と明記されています。
  * そのため、安全側の既定動作として **`ask_gemini` のデフォルトは `backend: "gemini"`（`GEMINI_API_KEY` 等の公式 API キー利用を推奨）** になっており、`agy` OAuth ブリッジはデフォルトで無効化されています。`agy` を利用する場合は、必ずご自身で利用規約をご確認のうえ、オプトイン（`allow_agy_oauth: true` または環境変数 `ALLOW_AGY_OAUTH_BRIDGE=1`）で自己責任にてご利用ください。
* **ファイル編集権限について**: `read_only: false` を指定すると、`codex` は `--sandbox workspace-write`、`agy` は `--mode auto --dangerously-skip-permissions` で起動します。**必ず Git 管理下で差分を確認しながら運用してください。**
* **秘密情報の取り扱い**: `.env`、APIキー、認証トークン、本番デプロイスクリプトなどを含むファイルはサブAIに渡さず、変更も司令塔（メインAI）のみで行ってください。
* **利用規約の遵守**: 本プロジェクトは各社の公式CLIをローカルから呼び出すラッパーです。各サービスの最新の利用規約および契約プランの上限の範囲内でご利用ください。

---

## ライセンス

[MIT License](LICENSE)

---

## クレジット

本リポジトリ（MCPブリッジ・オーケストレーションスキル・ドキュメント）は **Gemini 4 Hydrogen** を使用して開発しました。
