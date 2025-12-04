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
- **柔軟な設定**: 議員モデルと議長モデルを自由に設定可能
- **会話履歴管理**: 全ての評議会セッションをJSON形式で保存

## セットアップ

### 1. 環境変数の設定

`scripts/.env`ファイルを作成し、OpenRouter APIキーと使用するモデルを設定します:

```bash
cd scripts
cp .env.example .env
```

`.env`ファイルを編集:

```env
# OpenRouter API Configuration
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here

# Council Members - カンマ区切りのモデルリスト
COUNCIL_MODELS=openai/gpt-4,google/gemini-pro,anthropic/claude-3-5-sonnet-20241022,x-ai/grok-beta

# Chairman Model - 最終統合を行うモデル
CHAIRMAN_MODEL=anthropic/claude-3-5-sonnet-20241022
```

APIキーは[OpenRouter](https://openrouter.ai/)で取得できます。

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

### Git Worktreeを使用したコード作業

コードレビューや変更提案が必要な場合、`--worktrees`フラグを使用します:

```bash
python scripts/run.py council_skill.py "この関数のパフォーマンスを改善してください" --worktrees
```

このモードでは:
- 各議員が独立したgit worktreeで作業
- コード変更がdiffとして管理
- 匿名化されたdiffを相互レビュー
- 最終的な変更のみをメインブランチに統合

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
│   ├── council_skill.py       # メインエントリーポイント
│   ├── config.py              # 設定管理
│   ├── council.py             # 3段階評議会ロジック
│   ├── worktree_manager.py    # Git worktree管理
│   ├── openrouter_client.py   # OpenRouter APIクライアント
│   ├── storage.py             # 会話履歴保存
│   ├── .env                   # 環境変数(作成が必要)
│   ├── .env.example           # 環境変数テンプレート
│   ├── conversations/         # 会話履歴保存ディレクトリ
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
COUNCIL_MODELS=openai/gpt-4-turbo,anthropic/claude-3-opus,google/gemini-pro
```

### 議長モデルの変更

`scripts/.env`の`CHAIRMAN_MODEL`を編集:

```env
CHAIRMAN_MODEL=anthropic/claude-3-5-sonnet-20241022
```

### プロンプトのカスタマイズ

`scripts/prompts/templates.py`を編集して、各ステージのプロンプトをカスタマイズできます。

## トラブルシューティング

### "OPENROUTER_API_KEY not found"エラー

`scripts/.env`ファイルが存在し、有効なAPIキーが設定されていることを確認してください。

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

- [ ] Opencodeツールとの統合(コマンドベースのLLMインターフェース)
- [ ] より詳細な議員設定(温度パラメータ、専門分野など)
- [ ] リアルタイム進捗表示
- [ ] Webインターフェースの再実装(オプション)
