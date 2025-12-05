"""
LLM Council API Layer

Provides a clean API for the council functionality, suitable for both
CLI and web dashboard consumption.
"""

import uuid
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
from datetime import datetime

from logger import logger
from config import get_config
from council import CouncilOrchestrator
from storage import ConversationStorage


class SessionStatus(Enum):
    """Status of a council session."""
    IDLE = "idle"
    RUNNING = "running"
    STAGE1 = "stage1"
    STAGE2 = "stage2"
    STAGE3 = "stage3"
    MERGING = "merging"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class SessionProgress:
    """Progress information for a running session."""
    status: SessionStatus = SessionStatus.IDLE
    stage: int = 0
    stage_name: str = ""
    current_step: int = 0
    total_steps: int = 0
    message: str = ""
    member_statuses: Dict[str, str] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class MergeOptions:
    """Options for merging council results."""
    mode: Optional[str] = None  # None, "auto", "manual", "dry-run"
    member_index: Optional[int] = None  # For manual mode (1-based)
    confirm: bool = False
    no_commit: bool = False


class CouncilAPI:
    """
    High-level API for interacting with the LLM Council.
    
    This class provides a clean interface suitable for both CLI and web use.
    """
    
    def __init__(self, repo_root: Optional[Path] = None):
        """
        Initialize the Council API.
        
        Args:
            repo_root: Root directory of the git repository. If None, uses
                      the parent of the scripts directory.
        """
        if repo_root is None:
            repo_root = Path(__file__).parent.parent
        
        self.repo_root = repo_root
        self.config = get_config()
        self.storage = ConversationStorage(self.config.conversations_dir)
        self._orchestrator: Optional[CouncilOrchestrator] = None
        self._current_session: Optional[SessionProgress] = None
        self._progress_callbacks: List[Callable[[SessionProgress], None]] = []
    
    @property
    def orchestrator(self) -> CouncilOrchestrator:
        """Lazy initialization of orchestrator."""
        if self._orchestrator is None:
            self._orchestrator = CouncilOrchestrator(self.repo_root)
        return self._orchestrator
    
    # =========================================================================
    # Progress & Event Handling
    # =========================================================================
    
    def on_progress(self, callback: Callable[[SessionProgress], None]) -> None:
        """
        Register a callback for progress updates.
        
        Args:
            callback: Function to call with SessionProgress updates
        """
        self._progress_callbacks.append(callback)
    
    def _emit_progress(self, progress: SessionProgress) -> None:
        """Emit progress to all registered callbacks."""
        self._current_session = progress
        for callback in self._progress_callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
    
    # =========================================================================
    # Conversation Management
    # =========================================================================
    
    def list_conversations(self) -> List[Dict[str, Any]]:
        """
        List all stored conversations.
        
        Returns:
            List of conversation summaries with index, title, created_at, session_count
        """
        return self.storage.list_conversations()
    
    def get_conversation(self, index: int) -> Optional[Dict[str, Any]]:
        """
        Get a conversation by its display index.
        
        Args:
            index: 1-based conversation index
            
        Returns:
            Full conversation data or None if not found
        """
        return self.storage.get_conversation_by_index(index)
    
    def get_conversation_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a conversation by its UUID.
        
        Args:
            conversation_id: UUID of the conversation
            
        Returns:
            Full conversation data or None if not found
        """
        return self.storage.get_conversation(conversation_id)
    
    def delete_conversation(self, index: int) -> bool:
        """
        Delete a conversation by its display index.
        
        Args:
            index: 1-based conversation index
            
        Returns:
            True if deleted, False if not found
        """
        conversation_id = self.storage.get_conversation_id_by_index(index)
        if conversation_id:
            return self.storage.delete_conversation(conversation_id)
        return False
    
    # =========================================================================
    # Council Execution
    # =========================================================================
    
    def run_council(
        self,
        query: str,
        use_worktrees: bool = False,
        conversation_id: Optional[str] = None,
        merge_options: Optional[MergeOptions] = None
    ) -> Dict[str, Any]:
        """
        Run the LLM Council synchronously.
        
        Args:
            query: The user's question or request
            use_worktrees: Whether to use git worktrees for code work
            conversation_id: Optional existing conversation ID to continue
            merge_options: Options for merging changes
            
        Returns:
            Council results dictionary
        """
        return asyncio.run(self.run_council_async(
            query, use_worktrees, conversation_id, merge_options
        ))
    
    async def run_council_async(
        self,
        query: str,
        use_worktrees: bool = False,
        conversation_id: Optional[str] = None,
        merge_options: Optional[MergeOptions] = None
    ) -> Dict[str, Any]:
        """
        Run the LLM Council asynchronously.
        
        Args:
            query: The user's question or request
            use_worktrees: Whether to use git worktrees for code work
            conversation_id: Optional existing conversation ID to continue
            merge_options: Options for merging changes
            
        Returns:
            Council results dictionary
        """
        if merge_options is None:
            merge_options = MergeOptions()
        
        # Initialize progress
        progress = SessionProgress(
            status=SessionStatus.RUNNING,
            started_at=datetime.now(),
            message="Initializing council session..."
        )
        self._emit_progress(progress)
        
        try:
            # Get conversation history if continuing
            context_messages = []
            if conversation_id:
                context_messages = self.storage.get_conversation_history(conversation_id)
                if context_messages:
                    logger.info(f"Continuing conversation with {len(context_messages)} previous messages")
            
            # Run the full council
            results = await self.orchestrator.run_full_council(
                query,
                use_worktrees,
                context_messages=context_messages,
                merge_mode=merge_options.mode,
                merge_member=merge_options.member_index,
                confirm_merge=merge_options.confirm,
                no_commit=merge_options.no_commit
            )
            
            # Generate title for new conversations
            if conversation_id is None:
                progress.message = "Generating conversation title..."
                self._emit_progress(progress)
                
                title = await self.orchestrator.generate_conversation_title(query)
                conversation_id = str(uuid.uuid4())
                self.storage.add_session(conversation_id, query, results, title=title)
            else:
                self.storage.add_session(conversation_id, query, results)
            
            results["conversation_id"] = conversation_id
            
            # Mark completed
            progress.status = SessionStatus.COMPLETED
            progress.completed_at = datetime.now()
            progress.message = "Council session complete"
            self._emit_progress(progress)
            
            return results
            
        except Exception as e:
            progress.status = SessionStatus.ERROR
            progress.error = str(e)
            progress.completed_at = datetime.now()
            self._emit_progress(progress)
            raise
    
    def continue_conversation(
        self,
        index: int,
        query: str,
        use_worktrees: bool = False,
        merge_options: Optional[MergeOptions] = None
    ) -> Dict[str, Any]:
        """
        Continue an existing conversation.
        
        Args:
            index: 1-based conversation index
            query: The follow-up query
            use_worktrees: Whether to use git worktrees
            merge_options: Options for merging changes
            
        Returns:
            Council results dictionary
            
        Raises:
            ValueError: If conversation not found
        """
        conversation_id = self.storage.get_conversation_id_by_index(index)
        if conversation_id is None:
            raise ValueError(f"Conversation {index} not found")
        
        return self.run_council(
            query,
            use_worktrees=use_worktrees,
            conversation_id=conversation_id,
            merge_options=merge_options
        )
    
    # =========================================================================
    # Configuration & Status
    # =========================================================================
    
    def get_config_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current configuration.
        
        Returns:
            Dictionary with council members, chairman, etc.
        """
        members = self.config.get_council_members()
        chairman = self.config.get_chairman()
        
        return {
            "council_members": [
                {"full_name": m["full_name"], "provider": m["provider"]}
                for m in members
            ],
            "chairman": {
                "full_name": chairman["full_name"],
                "provider": chairman["provider"]
            },
            "worktrees_dir": str(self.config.worktrees_dir),
            "conversations_dir": str(self.config.conversations_dir),
            "logs_dir": str(self.config.logs_dir)
        }
    
    def get_current_progress(self) -> Optional[SessionProgress]:
        """
        Get the current session progress.
        
        Returns:
            Current SessionProgress or None if no session
        """
        return self._current_session
    
    def get_setup_instructions(self) -> str:
        """
        Get setup instructions text.
        
        Returns:
            Setup instructions as a string
        """
        return """
LLM Council Setup Instructions:

1. Create a .env file in the scripts/ directory:
   cd scripts
   cp .env.example .env

2. Configure council members and chairman model in .env:
   COUNCIL_MODELS=opencode/openai/gpt-4,opencode/anthropic/claude-3-5-sonnet-20241022,...
   CHAIRMAN_MODEL=opencode/anthropic/claude-3-5-sonnet-20241022
   
   Note: All models use OpenCode CLI. Format is opencode/provider/model
   You can also omit 'opencode/' prefix as it's the default.

3. Install dependencies:
   pip install python-dotenv loguru

4. Run the council:
   python council_skill.py "Your query here"

5. Continue a conversation:
   python council_skill.py --list
   python council_skill.py --continue 1 "Follow-up question"

For more information, see README.md
        """.strip()


# Singleton instance for convenience
_api_instance: Optional[CouncilAPI] = None


def get_api(repo_root: Optional[Path] = None) -> CouncilAPI:
    """
    Get the singleton CouncilAPI instance.
    
    Args:
        repo_root: Root directory of the git repository
        
    Returns:
        CouncilAPI instance
    """
    global _api_instance
    if _api_instance is None:
        _api_instance = CouncilAPI(repo_root)
    return _api_instance
