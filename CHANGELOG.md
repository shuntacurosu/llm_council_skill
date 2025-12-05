# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
