# LLM Council - Claude Skill

![LLM Council Header](refs/header.jpg)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)

[English](./README.md) | [日本語](./README.ja.md)

A Claude Skill that orchestrates multiple LLMs as a "council" to achieve collective intelligence through peer review and synthesis.

## Overview

LLM Council organizes multiple LLMs as a "council" instead of querying a single LLM, deriving conclusions through a 3-stage process:

1. **Stage 1: Opinion Collection** - Each council member (LLM) independently responds to the query
2. **Stage 2: Peer Review** - Each member anonymously reviews and ranks other members' responses
3. **Stage 3: Final Synthesis** - The Chairman LLM integrates all opinions and reviews into the final response

### Key Features

- **Git Worktree Integration**: Manage each member's work in independent git worktrees
- **Anonymous Review**: Member identities are anonymized in Stage 2 for fair evaluation
- **OpenCode CLI Integration**: Generate and edit code directly within worktrees
- **Flexible Configuration**: Freely configure member models and chairman model
- **Real-time Dashboard**: TUI dashboard showing member status, stage progress, and live logs
- **Conversation History**: Save all council sessions in JSON format

### Dashboard

Monitor council sessions in real-time with the built-in TUI dashboard:

![Dashboard](refs/dashboard.jpg)

The dashboard displays:
- **Stage Flow**: Visual progress indicator showing current stage (`[1] Responses ━━▶ [2] Rankings ━━▶ [3] Synthesis`)
- **Member Status**: Real-time status of each council member (🟢 Active, ⏳ Waiting, ✅ Completed, ❌ Error)
- **Live Logs**: Latest 15 log entries scrolling in real-time
- **Statistics**: API call count, errors, and session info

Enable with `--dashboard` or `-d` flag:
```bash
python scripts/run.py cli.py --dashboard "Your question"
```

## Setup

### 1. Environment Variables

Create a `scripts/.env` file to configure the models:

```bash
cd scripts
cp .env.example .env
```

Edit `.env`:

```env
# Council Members - comma-separated provider/model list
# Format: opencode/provider/model (or provider/model, defaults to opencode)
# Examples:
#   opencode/openrouter/openai/gpt-4
#   opencode/anthropic/claude-3-5-sonnet-20241022
#   anthropic/claude-3-5-sonnet-20241022  (opencode prefix can be omitted)
COUNCIL_MODELS=opencode/openai/gpt-4,opencode/anthropic/claude-3-5-sonnet,opencode/google/gemini-pro

# Chairman Model - performs final synthesis
CHAIRMAN_MODEL=opencode/anthropic/claude-3-5-sonnet

# Title Generation Model - for conversation titles (optional, defaults to CHAIRMAN_MODEL)
# TITLE_MODEL=opencode/anthropic/claude-3-5-haiku-20241022

# Dashboard Settings (optional)
DASHBOARD_TIMEOUT=5       # Seconds to show dashboard after completion
DASHBOARD_REFRESH_RATE=10 # Dashboard refresh rate in Hz
```

### About OpenCode CLI

This tool uses [OpenCode CLI](https://github.com/sst/opencode) to interact with LLMs.
OpenCode must be installed and properly configured.

**Note**: Future support for other CLI tools like claude-code and codex is planned.

### 2. Virtual Environment (Automatic)

A virtual environment is automatically created on first run with dependencies installed.

To manually set up the virtual environment:

```bash
python scripts/setup_environment.py
```

### 3. Git Repository

This tool uses git worktrees, so it must be run within a git repository.

## Usage

### Basic Usage (Recommended)

Using `run.py` automatically sets up the virtual environment and runs the script with the correct Python environment:

```bash
python scripts/run.py council_skill.py "Enter your question here"
```

Example:
```bash
python scripts/run.py council_skill.py "What is the best approach to implement caching in a web application?"
```

### Command Line Options

#### Basic Options

| Option | Description | Example |
|--------|-------------|---------|
| `query` | Question to send to the council (positional) | `"Your question"` |
| `--dashboard`, `-d` | Enable TUI dashboard for real-time monitoring | `--dashboard` |
| `--worktrees` | Enable Git worktree mode | `--worktrees` |
| `--list` | Show conversation history | `--list` |
| `--show N` | Show details of conversation N | `--show 1` |
| `--continue N` | Continue conversation N | `--continue 1 "Follow-up"` |
| `--setup` | Show setup guide | `--setup` |

#### Merge Options (with `--worktrees`)

| Option | Description | Example |
|--------|-------------|---------|
| `--auto-merge` | Auto-merge the top-ranked proposal | `--auto-merge` |
| `--merge N` | Merge member N's proposal | `--merge 2` |
| `--dry-run` | Show diff without merging | `--dry-run` |
| `--confirm` | Show confirmation before merge | `--auto-merge --confirm` |
| `--no-commit` | Apply without staging | `--auto-merge --no-commit` |

#### Examples

```bash
# Basic question
python scripts/run.py council_skill.py "What's the optimal caching strategy?"

# Code fix (diff only)
python scripts/run.py council_skill.py --dry-run "Fix the bug in buggy.py"

# Code fix (auto-merge with confirmation)
python scripts/run.py council_skill.py --auto-merge --confirm "Add error handling to divide function"

# Code fix (auto-merge without commit)
python scripts/run.py council_skill.py --auto-merge --no-commit "Add tests"

# Merge specific member's proposal
python scripts/run.py council_skill.py --merge 2 "Refactor this"

# Continue conversation
python scripts/run.py council_skill.py --continue 1 "Tell me more"
```

### View Conversation History

```bash
python scripts/run.py council_skill.py --list
```

### Show Setup Guide

```bash
python scripts/run.py council_skill.py --setup
```

### Check Virtual Environment Status

```bash
python scripts/setup_environment.py --check
```

## Project Structure

```
llm_council/
├── .venv/                     # Virtual environment (auto-created)
├── scripts/
│   ├── __init__.py
│   ├── run.py                 # Run scripts via virtual environment
│   ├── setup_environment.py   # Virtual environment setup
│   ├── council_skill.py       # Main entry point (backward compatible)
│   ├── api.py                 # High-level API (for dashboard)
│   ├── cli.py                 # CLI interface
│   ├── config.py              # Configuration management
│   ├── council.py             # 3-stage council logic
│   ├── dashboard.py           # TUI dashboard (Rich-based)
│   ├── worktree_manager.py    # Git worktree management
│   ├── unified_client.py      # Unified LLM client
│   ├── opencode_client.py     # OpenCode CLI client
│   ├── storage.py             # Conversation history storage
│   ├── logger.py              # Logging configuration
│   ├── .env                   # Environment variables (create this)
│   ├── .env.example           # Environment variables template
│   ├── data/
│   │   ├── conversations/     # Conversation history JSON
│   │   └── logs/              # Execution logs
│   ├── prompts/
│   │   └── templates.py       # Prompt templates
│   └── worktrees/             # Git worktree directory
├── requirements.txt           # Python dependencies
├── skill.json                 # Claude Skill definition
└── README.md                  # This file
```

## How It Works

### Stage 1: Opinion Collection

Each council member (configured LLM model) independently responds to the user's query.

- Normal mode: Text-based responses
- Worktree mode: Each member works in an independent worktree to generate code changes

### Stage 2: Peer Review

All members anonymously review other members' responses.

- Responses are anonymized as "Response A", "Response B", etc.
- Each member evaluates and ranks all responses
- Aggregate scores are calculated to generate overall rankings

### Stage 3: Final Synthesis

The chairman model integrates all opinions and review results to generate the final response.

- Considers strengths of each member's opinion
- Reflects issues identified in peer review
- Analyzes consensus patterns and differences
- Provides a clear final response representing the council's collective intelligence

## Customization

### Changing Council Members

Edit `COUNCIL_MODELS` in `scripts/.env`:

```env
COUNCIL_MODELS=opencode/openai/gpt-4-turbo,opencode/anthropic/claude-3-opus,opencode/google/gemini-pro
```

### Changing Chairman Model

Edit `CHAIRMAN_MODEL` in `scripts/.env`:

```env
CHAIRMAN_MODEL=opencode/anthropic/claude-3-5-sonnet
```

### Customizing Prompts

Edit `scripts/prompts/templates.py` to customize prompts for each stage.

## Troubleshooting

### "not a git repository" Error

This tool must be run within a git repository. Initialize with `git init`.

### Removing Worktrees

If worktrees remain for some reason:

```bash
git worktree prune
```

Or manually:

```bash
rm -rf scripts/worktrees/*
git worktree prune
```

## License

MIT License

## Acknowledgments

This project is inspired by [Andrej Karpathy's llm-council](https://github.com/karpathy/llm-council).

## Future Plans

- [x] ~~OpenCode tool integration (command-based LLM interface)~~
- [x] ~~Real-time progress display~~
- [x] ~~TUI Dashboard with Rich~~
- [ ] More detailed member settings (temperature parameters, expertise areas, etc.)
- [ ] Web interface (optional)
