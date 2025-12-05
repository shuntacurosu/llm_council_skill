# LLM Council - Claude Skill

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)

複数のLLMを「議員」に見立て、集合知による意思決定を行うClaude Skillです。

## 概要

LLM Councilは、単一のLLMに質問するのではなく、複数のLLMを「評議会」として組織し、以下の3段階プロセスで結論を導き出します:

1. **Stage 1: 初回意見収集** - 各議員(LLM)が独立して質問に回答
2. **Stage 2: 相互レビュー** - 各議員が他の議員の回答を匿名でレビュー・ランキング
3. **Stage 3: 最終統合** - 議長(Chairman LLM)が全ての意見とレビューを統合して最終回答を生成

### 主な特徴

- **Git Worktree統合**: 各議員の作業を独立したgit worktreeで管理
- **匿名レビュー**: Stage 2では議員の身元を匿名化して公平なレビューを実現
- **OpenCode CLI統合**: ワークツリー内でコードを直接生成・編集
- **柔軟な設定**: 議員モデルと議長モデルを自由に設定可能
- **リアルタイム進捗表示**: 各モデルのクエリ状態をリアルタイムで表示
- **会話履歴管理**: 全ての評議会セッションをJSON形式で保存

## セットアップ

### 1. 環境変数の設定

`scripts/.env`ファイルを作成し、使用するモデルを設定します:

```bash
cd scripts
cp .env.example .env
```

`.env`ファイルを編集:

```env
# Council Members - カンマ区切りのprovider/modelリスト
# 形式: opencode/provider/model (またはprovider/model、デフォルトでopencode)
# 例:
#   opencode/openrouter/openai/gpt-4
#   opencode/anthropic/claude-3-5-sonnet-20241022
#   anthropic/claude-3-5-sonnet-20241022  (opencodeプレフィックスは省略可)
COUNCIL_MODELS=opencode/openai/gpt-4,opencode/anthropic/claude-3-5-sonnet,opencode/google/gemini-pro

# Chairman Model - 最終統合を行うモデル
CHAIRMAN_MODEL=opencode/anthropic/claude-3-5-sonnet

# Title Generation Model - 会話タイトル生成用 (オプション、デフォルトはCHAIRMAN_MODEL)
# TITLE_MODEL=opencode/anthropic/claude-3-5-haiku-20241022
```

### OpenCode CLIについて

このツールは[OpenCode CLI](https://github.com/sst/opencode)を使用してLLMとやり取りします。
OpenCodeがインストールされ、適切に設定されている必要があります。

**注意**: 将来的にclaude-code、codexなど他のCLIツールもサポート予定です。

### 2. 仮想環境の作成（自動）

初回実行時に自動で仮想環境が作成され、依存関係がインストールされます。

手動で仮想環境をセットアップする場合:

```bash
python scripts/setup_environment.py
```

### 3. Gitリポジトリの確認

このツールはgit worktreeを使用するため、gitリポジトリ内で実行する必要があります。

## 使用方法

### 基本的な使用（推奨）

`run.py`を使用すると、仮想環境が自動でセットアップされ、正しいPython環境でスクリプトが実行されます:

```bash
python scripts/run.py council_skill.py "質問をここに入力"
```

例:
```bash
python scripts/run.py council_skill.py "Webアプリケーションにキャッシングを実装する最適なアプローチは何ですか?"
```

### コマンドラインオプション

#### 基本オプション

| オプション | 説明 | 例 |
|------------|------|-----|
| `query` | 評議会に送る質問（位置引数） | `"質問内容"` |
| `--worktrees` | Git worktreeモードを有効化 | `--worktrees` |
| `--list` | 会話履歴の一覧を表示 | `--list` |
| `--show N` | 会話Nの詳細を表示 | `--show 1` |
| `--continue N` | 会話Nを継続 | `--continue 1 "追加質問"` |
| `--setup` | セットアップガイドを表示 | `--setup` |

#### マージオプション（`--worktrees` 使用時）

| オプション | 説明 | 例 |
|------------|------|-----|
| `--auto-merge` | 1位の提案を自動マージ | `--auto-merge` |
| `--merge N` | メンバーNの提案をマージ | `--merge 2` |
| `--dry-run` | マージせず差分のみ表示 | `--dry-run` |
| `--confirm` | マージ前に確認プロンプト表示 | `--auto-merge --confirm` |
| `--no-commit` | 変更をステージングせず適用 | `--auto-merge --no-commit` |

#### 使用例

```bash
# 基本的な質問
python scripts/run.py council_skill.py "最適なキャッシュ戦略は？"

# コード修正（差分確認のみ）
python scripts/run.py council_skill.py --dry-run "buggy.pyのバグを修正して"

# コード修正（自動マージ、確認あり）
python scripts/run.py council_skill.py --auto-merge --confirm "divide関数にエラー処理を追加"

# コード修正（自動マージ、コミットなし）
python scripts/run.py council_skill.py --auto-merge --no-commit "テスト追加"

# 特定メンバーの提案をマージ
python scripts/run.py council_skill.py --merge 2 "リファクタリング"

# 会話の継続
python scripts/run.py council_skill.py --continue 1 "もう少し詳しく"
```

### 会話履歴の確認

```bash
python scripts/run.py council_skill.py --list
```

### セットアップガイドの表示

```bash
python scripts/run.py council_skill.py --setup
```

### 仮想環境の状態確認

```bash
python scripts/setup_environment.py --check
```

## プロジェクト構造

```
llm_council/
├── .venv/                     # 仮想環境(自動作成)
├── scripts/
│   ├── __init__.py
│   ├── run.py                 # 仮想環境経由でスクリプトを実行
│   ├── setup_environment.py   # 仮想環境セットアップ
│   ├── council_skill.py       # メインエントリーポイント（後方互換）
│   ├── api.py                 # 高レベルAPI（ダッシュボード向け）
│   ├── cli.py                 # CLIインターフェース
│   ├── config.py              # 設定管理
│   ├── council.py             # 3段階評議会ロジック
│   ├── worktree_manager.py    # Git worktree管理
│   ├── unified_client.py      # 統合LLMクライアント
│   ├── opencode_client.py     # OpenCode CLIクライアント
│   ├── storage.py             # 会話履歴保存
│   ├── logger.py              # ログ設定
│   ├── .env                   # 環境変数(作成が必要)
│   ├── .env.example           # 環境変数テンプレート
│   ├── data/
│   │   ├── conversations/     # 会話履歴JSON
│   │   └── logs/              # 実行ログ
│   ├── prompts/
│   │   └── templates.py       # プロンプトテンプレート
│   └── worktrees/             # Git worktreeディレクトリ
├── requirements.txt           # Python依存関係
├── skill.json                 # Claude Skill定義
└── README.md                  # このファイル
```

## 動作の詳細

### Stage 1: 初回意見収集

各議員(設定されたLLMモデル)が、ユーザーの質問に対して独立して回答します。

- 通常モード: テキストベースの回答
- Worktreeモード: 各議員が独立したworktreeで作業し、コード変更を生成

### Stage 2: 相互レビュー

全ての議員が、他の議員の回答を匿名でレビューします。

- 回答は「Response A」「Response B」などと匿名化
- 各議員が全ての回答を評価し、ランキングを提供
- 集計スコアを計算して総合ランキングを生成

### Stage 3: 最終統合

議長モデルが、全ての意見とレビュー結果を統合して、最終的な回答を生成します。

- 各議員の意見の強みを考慮
- ピアレビューで明らかになった問題点を反映
- 合意パターンや相違点を分析
- 評議会の集合知を表す明確な最終回答を提供

## カスタマイズ

### 議員モデルの変更

`scripts/.env`の`COUNCIL_MODELS`を編集:

```env
COUNCIL_MODELS=opencode/openai/gpt-4-turbo,opencode/anthropic/claude-3-opus,opencode/google/gemini-pro
```

### 議長モデルの変更

`scripts/.env`の`CHAIRMAN_MODEL`を編集:

```env
CHAIRMAN_MODEL=opencode/anthropic/claude-3-5-sonnet
```

### プロンプトのカスタマイズ

`scripts/prompts/templates.py`を編集して、各ステージのプロンプトをカスタマイズできます。

## トラブルシューティング

### "not a git repository"エラー

このツールはgitリポジトリ内で実行する必要があります。`git init`でリポジトリを初期化してください。

### Worktreeの削除

何らかの理由でworktreeが残っている場合:

```bash
git worktree prune
```

または手動で:

```bash
rm -rf scripts/worktrees/*
git worktree prune
```

## ライセンス

MIT License

## 謝辞

このプロジェクトは[Andrej Karpathy氏のllm-council](https://github.com/karpathy/llm-council)にインスパイアされています。

## 今後の拡張予定

- [x] ~~Opencodeツールとの統合(コマンドベースのLLMインターフェース)~~
- [x] ~~リアルタイム進捗表示~~
- [ ] より詳細な議員設定(温度パラメータ、専門分野など)
- [ ] Webインターフェースの再実装(オプション)
