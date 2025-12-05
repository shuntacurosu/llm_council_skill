# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-12-06

### Added
- **TUI Dashboard** (`--dashboard` / `-d`)
  - Real-time monitoring of council sessions with Rich-based TUI
  - Stage flow visualization: `[1] Responses ━━▶ [2] Rankings ━━▶ [3] Synthesis`
  - Active stage highlighted with color (yellow on blue background)
  - Completed stages shown in green with checkmark
  - Member status panel with real-time icons (🟢 Active, ⏳ Waiting, ✅ Completed, ❌ Error)
  - Live logs panel showing latest 15 entries (scrolling, newest at bottom)
  - Statistics panel with API call count, errors, and log count
  - Dynamic layout adapting to member count
  - Countdown timer on completion before auto-close

- **Dashboard Configuration**
  - `DASHBOARD_TIMEOUT`: Seconds to display dashboard after completion (default: 5)
  - `DASHBOARD_REFRESH_RATE`: Dashboard refresh rate in Hz (default: 10)

### Changed
- Updated README.md, README.ja.md, SKILL.md with dashboard documentation
- Added `dashboard.py` to project structure
- Added `rich>=13.0.0` to dependencies

## [1.0.0] - 2025-12-06

### Added
- **3-Stage Council Process**
  - Stage 1: Independent opinion collection from multiple LLMs
  - Stage 2: Anonymous peer review and ranking
  - Stage 3: Chairman synthesis of final response

- **Git Worktree Integration**
  - Each council member works in isolated git worktrees
  - Automatic worktree creation and cleanup
  - Untracked file detection support

- **Merge Options**
  - `--auto-merge`: Automatically merge top-ranked proposal
  - `--merge N`: Merge specific member's proposal
  - `--dry-run`: Preview diff without applying changes
  - `--confirm`: Interactive confirmation before merge
  - `--no-commit`: Apply changes without staging

- **Conversation Management**
  - `--list`: View conversation history
  - `--show N`: Display conversation details
  - `--continue N`: Continue previous conversation
  - JSON-based conversation storage

- **CLI Features**
  - `--setup`: Display setup guide
  - `--worktrees`: Enable worktree mode for code tasks
  - Real-time progress display for each model

- **Architecture**
  - OpenCode CLI integration for LLM interactions
  - Unified client abstraction for future CLI support
  - API layer (`api.py`) for dashboard integration
  - Automatic virtual environment setup

### Technical
- Python 3.8+ support
- Dependencies: httpx, python-dotenv, loguru
- Claude Skill format (`SKILL.md`)
