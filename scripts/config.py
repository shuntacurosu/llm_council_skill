"""Configuration management for LLM Council."""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Get the scripts directory
SCRIPTS_DIR = Path(__file__).parent.parent
ENV_PATH = SCRIPTS_DIR / ".env"

# Load environment variables
load_dotenv(ENV_PATH)


class Config:
    """Configuration for LLM Council."""
    
    def __init__(self):
        self.scripts_dir = SCRIPTS_DIR
        self.conversations_dir = SCRIPTS_DIR / "conversations"
        self.prompts_dir = SCRIPTS_DIR / "prompts"
        self.worktrees_dir = SCRIPTS_DIR / "worktrees"
        
        # Ensure directories exist
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)
        
        # API Configuration
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY not found in .env file")
        
        # Model Configuration
        council_models_str = os.getenv("COUNCIL_MODELS", "")
        self.council_models = [
            model.strip() 
            for model in council_models_str.split(",") 
            if model.strip()
        ]
        
        if not self.council_models:
            raise ValueError("COUNCIL_MODELS not found or empty in .env file")
        
        self.chairman_model = os.getenv("CHAIRMAN_MODEL")
        if not self.chairman_model:
            raise ValueError("CHAIRMAN_MODEL not found in .env file")
        
        # OpenRouter API endpoint
        self.openrouter_api_url = "https://openrouter.ai/api/v1/chat/completions"
    
    @property
    def council_member_count(self) -> int:
        """Get the number of council members."""
        return len(self.council_models)
    
    def get_council_models(self) -> List[str]:
        """Get the list of council member models."""
        return self.council_models.copy()
    
    def get_chairman_model(self) -> str:
        """Get the chairman model."""
        return self.chairman_model


# Global config instance
_config = None

def get_config() -> Config:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
