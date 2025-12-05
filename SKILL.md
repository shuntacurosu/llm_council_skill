---
name: LLM Council
description: 複数のLLMを評議会として組織し、相互レビューと議長統合により集合知の最終回答を生成
version: 1.0.0
dependencies: python>=3.8, python-dotenv, loguru
---

## Overview

LLM Councilは、複数のLLMを「議員」として組織し、3段階プロセスで高品質な回答を生成するSkillです。

### 使用シーン

- 重要な意思決定に複数の視点が欲しいとき
- コードレビューを複数のAIに依頼したいとき
- 設計案を比較検討したいとき
- バイアスを減らした客観的な回答が必要なとき

## 3-Stage Process

1. **Stage 1: 意見収集** - 各議員(LLM)が独立して回答
2. **Stage 2: 相互レビュー** - 匿名化された回答を相互にランキング
3. **Stage 3: 統合** - 議長が全意見とレビューを統合して最終回答を生成

## Quick Start

```bash
# 基本的な質問
python scripts/run.py council_skill.py "最適なキャッシュ戦略は？"

# コード修正（差分確認のみ）
python scripts/run.py council_skill.py --dry-run "buggy.pyのバグを修正して"

# 自動マージ
python scripts/run.py council_skill.py --auto-merge "エラー処理を追加して"
```

## Command Options

| Option | Description |
|--------|-------------|
| `--worktrees` | Git worktreeモードで各議員が独立して作業 |
| `--dry-run` | マージせず差分のみ表示 |
| `--auto-merge` | 1位の提案を自動マージ |
| `--merge N` | メンバーNの提案をマージ |
| `--confirm` | マージ前に確認プロンプト |
| `--no-commit` | 変更をステージングせず適用 |
| `--list` | 会話履歴の一覧表示 |
| `--continue N` | 会話Nを継続 |

## Setup

1. `scripts/.env`を作成してモデルを設定
2. OpenCode CLIをインストール・設定
3. `python scripts/run.py council_skill.py --setup`で詳細確認

## Resources

詳細は`README.md`を参照してください。
