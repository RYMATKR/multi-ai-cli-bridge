---
name: multi-ai-orchestrator
description: >-
  Orchestrate software development across Claude Code, OpenAI Codex, and
  Antigravity/Gemini using role-based delegation via MCP (`multi-ai-cli-bridge`)
  or local CLIs. Use this skill when the user asks to collaborate across multiple
  AIs, divide implementation/review roles, or run a multi-model workflow.
---

# Multi-AI Orchestrator

このスキルは、**Claude Code**・**OpenAI Codex**・**Antigravity / Gemini** の3つ（または利用可能な2つ）を協調させ、1つの依頼から設計・実装・レビューを分担して進めるための実行手順です。
司令塔のトークン消費を抑えるため、**1ファイル1AI担当のルールのもとでサブAIにもファイル書き込みを委譲**します。

---

## 1. 基本原則（トークン節約・競合防止・安全）

1. **1ファイル1AI担当で書き込みを委譲する（`read_only: false`）**
   * 司令塔（特に Claude Code）は「設計・タスク分割・境界定義・差分確認・テスト」に集中し、実装作業は `ask_gemini` / `ask_codex` に `read_only: false` で直接ファイルを書かせてよい。
   * **競合防止ルール**：同じファイルを複数のAIに同時に書かせない。依頼時に「**書いてよいファイル／フォルダ**」を明記し、それ以外は読み取りのみとさせる。
   * **レビュー・調査時は `read_only: true`**：設計レビュー・調査・クロスレビューでは必ず `read_only: true` を使う。
2. **秘密情報・本番/配布操作は司令塔のみ**
   * 鍵・トークン・パスワードを含むファイル、設定ファイル（`secrets`, `settings.cfg`, `config.toml`, `mcp.json` 等）、デプロイ／本番反映スクリプトはサブAIに渡さず、変更も司令塔のみが行う。
3. **Windows 環境の UTF-8 ルール**
   * サブAIへのプロンプトには、**「日本語を含むファイルの読み書きは必ず UTF-8 指定で行うこと」** を明記する。
4. **サブスク枠（OAuth）と残量確認**
   * MCPツールはデフォルトで `use_subscription_only: true`（APIキー除外）で動作する。
   * 実行前の確認には `check_usage` を使い、実行後は返答末尾の `[Quota Remaining]` を確認して残量に応じて負荷を調整する。
5. **レートリミット・未インストール時の動的フォールバック**
   * 最初に `check_ai_agents` を実行し、利用可能なAIを確認する。
   * 特定のAIが上限・エラー等で止まった場合は、**残りのAIへ役割を再配分**して続行する。

---

## 2. 役割分担マトリクス

現在対話しているAI（自分自身）を **Orchestrator（司令塔）** とし、残りのタスクを以下の得意領域で振り分ける。

| AI | 得意領域 | 任せるべきタスク例 |
| :--- | :--- | :--- |
| **Claude Code** | 全体設計、境界定義、差分統合、テスト | タスク分割、API/関数シグネチャ定義、差分検証、テスト実行、秘密・配布ファイル管理 |
| **Antigravity (`agy`)** | 大きめの実装、全体調査、設計/コードレビュー | 新規モジュールや画面1つ分の実装（`read_only: false`）、リポジトリ横断調査、他AIコードのレビュー |
| **Codex** | 小さく閉じた実装、テスト、エッジケース | 関数1つ・ヘルパー実装（`read_only: false`）、ユニットテスト作成、バグ切り分け（上限に配慮し1回で終わる単位に小分け） |

---

## 3. 実行ワークフロー

### Phase 0: 稼働・残量確認
1. `check_ai_agents` で利用可能なCLIを確認し、必要に応じて `check_usage` で残り枠を確認する。

### Phase 1: 設計・境界定義
1. 最初に `get_repo_summary` で不要ディレクトリを除外した軽量リポジトリ要約（キャッシュ）を取得し、全体を把握する。
2. 司令塔が要件を整理し、担当ファイルとインターフェース（関数名・型・入出力）を決める。
3. 規模が大きい場合は、実装前に `ask_gemini`（`read_only: true`）でリポジトリ調査や設計レビューを行う。

### Phase 2: 分担実装（`read_only: false`）
1. 担当ファイルが重複しないように切り分けて `ask_gemini` / `ask_codex` に実装を委譲する。
2. プロンプトには必ず以下を含める：
   * 書いてよいファイル（またはフォルダ）のパス
   * 満たすべき仕様・インターフェース
   * 既存コードの規約（日本語コメント・命名規則など）
   * **「日本語ファイルは必ず UTF-8 で読み書きすること」**
   * 「完了後に変更したファイル一覧と要約を返すこと」

### Phase 3: 差分確認・クロスレビュー・テスト
1. 司令塔が `git diff` やファイル内容を確認し、問題がないか検証する。
2. 重要な変更は、実装を担当しなかった側のAIに `read_only: true` でクロスレビューを依頼する。
3. 司令塔がテストを実行し、すべてのテストが通った状態で、**どのAIに何を頼みどう使ったか**を添えてユーザーに報告する。
