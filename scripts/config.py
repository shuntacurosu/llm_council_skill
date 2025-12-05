"""Configuration management for LLM Council."""

import os
from pathlib import Path
from typing import List, Tuple
from dotenv import load_dotenv

# Get the scripts directory
SCRIPTS_DIR = Path(__file__).parent
ENV_PATH = SCRIPTS_DIR / ".env"

# Load environment variables
load_dotenv(ENV_PATH)


def parse_provider_model(full_model: str) -> Tuple[str, str]:
    """
    Parse a provider/model string.
    
    Format: provider/model_path
    Examples:
        - opencode/anthropic/claude-3 -> ("opencode", "anthropic/claude-3")
        - anthropic/claude-3 -> ("opencode", "anthropic/claude-3")  # default to opencode
    
    Note:
        Future support for other CLIs (claude-code, codex) may be added.
    
    Returns:
        Tuple of (provider, model)
    """
    parts = full_model.split("/", 1)
    if len(parts) < 2:
        raise ValueError(f"Invalid model format: {full_model}. Expected 'provider/model'")
    
    provider = parts[0].lower()
    
    # Check if it's a known provider prefix
    known_providers = ["opencode"]  # Only opencode supported
    if provider in known_providers:
        # Extract the rest as model
        remaining = parts[1]
        return (provider, remaining)
    else:
        # Default to opencode if not a known provider
        return ("opencode", full_model)


class Config:
    """Configuration for LLM Council."""
    
    def __init__(self):
        self.scripts_dir = SCRIPTS_DIR
        
        # Data directory structure (for dashboard integration)
        self.data_dir = SCRIPTS_DIR / "data"
        self.logs_dir = self.data_dir / "logs"
        self.conversations_dir = self.data_dir / "conversations"
        self.worktrees_dir = SCRIPTS_DIR / "worktrees"
        
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)
        
        # Model Configuration - now supports provider/model format
        council_models_str = os.getenv("COUNCIL_MODELS", "")
        self.council_models_raw = [
            model.strip() 
            for model in council_models_str.split(",") 
            if model.strip()
        ]
        
        if not self.council_models_raw:
            raise ValueError("COUNCIL_MODELS not found or empty in .env file")
        
        # Parse provider/model for each council member
        self.council_members = []
        for model_str in self.council_models_raw:
            provider, model = parse_provider_model(model_str)
            self.council_members.append({
                "provider": provider,
                "model": model,
                "full_name": model_str
            })
        
        # Chairman model
        chairman_model_str = os.getenv("CHAIRMAN_MODEL")
        if not chairman_model_str:
            raise ValueError("CHAIRMAN_MODEL not found in .env file")
        
        chairman_provider, chairman_model = parse_provider_model(chairman_model_str)
        self.chairman = {
            "provider": chairman_provider,
            "model": chairman_model,
            "full_name": chairman_model_str
        }
        
        # Title generation model (optional, defaults to chairman model)
        title_model_str = os.getenv("TITLE_MODEL", chairman_model_str)
        title_provider, title_model = parse_provider_model(title_model_str)
        self.title_model = {
            "provider": title_provider,
            "model": title_model,
            "full_name": title_model_str
        }
    
    @property
    def council_member_count(self) -> int:
        """Get the number of council members."""
        return len(self.council_members)
    
    def get_council_members(self) -> List[dict]:
        """Get the list of council members with provider info."""
        return self.council_members.copy()
    
    def get_council_models(self) -> List[str]:
        """Get the list of council member full names (for backward compatibility)."""
        return [m["full_name"] for m in self.council_members]
    
    def get_chairman(self) -> dict:
        """Get the chairman with provider info."""
        return self.chairman.copy()
    
    def get_chairman_model(self) -> str:
        """Get the chairman model full name (for backward compatibility)."""
        return self.chairman["full_name"]
    
    def get_title_model(self) -> dict:
        """Get the title generation model with provider info."""
        return self.title_model.copy()


# Global config instance
_config = None

def get_config() -> Config:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
