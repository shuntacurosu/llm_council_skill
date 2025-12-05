"""Unified LLM client - OpenCode CLI only."""

import asyncio
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from pathlib import Path

from logger import logger, get_member_logger
from opencode_client import OpenCodeClient

if TYPE_CHECKING:
    from dashboard import CouncilDashboard, MemberStatus


class UnifiedLLMClient:
    """
    Unified client that routes requests to OpenCode CLI.
    
    Supports:
        - opencode: OpenCode CLI (primary and only provider)
    
    Note:
        Future support for other CLIs (claude-code, codex) may be added.
    """
    
    def __init__(
        self,
        working_dir: Optional[Path] = None,
        dashboard: Optional["CouncilDashboard"] = None
    ):
        """
        Initialize the unified client.
        
        Args:
            working_dir: Working directory for OpenCode
            dashboard: Optional dashboard for live updates
        """
        self.opencode_client = OpenCodeClient(working_dir=working_dir)
        self.dashboard = dashboard
    
    def set_dashboard(self, dashboard: Optional["CouncilDashboard"]) -> None:
        """Set the dashboard for live updates."""
        self.dashboard = dashboard
    
    def _notify_dashboard(
        self,
        member_id: str,
        status: Optional[str] = None,
        activity: Optional[str] = None,
        api_calls_delta: int = 0,
        error: Optional[str] = None
    ) -> None:
        """Notify dashboard of member status change."""
        if self.dashboard is None:
            return
        
        from dashboard import MemberStatus
        
        status_map = {
            "active": MemberStatus.ACTIVE,
            "waiting": MemberStatus.WAITING,
            "completed": MemberStatus.COMPLETED,
            "error": MemberStatus.ERROR,
            "idle": MemberStatus.IDLE,
        }
        
        member_status = status_map.get(status) if status else None
        self.dashboard.update_member(
            member_id,
            status=member_status,
            activity=activity,
            api_calls_delta=api_calls_delta,
            error=error
        )
        self.dashboard.refresh()
    
    async def query_member(
        self,
        member: Dict[str, str],
        messages: List[Dict[str, str]],
        working_dir: Optional[Path] = None,
        timeout: float = 300.0
    ) -> Optional[Dict[str, Any]]:
        """
        Query a council member using OpenCode CLI.
        
        Args:
            member: Dict with 'provider', 'model', 'full_name' keys
            messages: List of message dicts
            working_dir: Working directory for OpenCode
            timeout: Request timeout
            
        Returns:
            Response dict with 'content' and 'model', or None if failed
        """
        provider = member["provider"]
        model = member["model"]
        full_name = member["full_name"]
        
        # Create a stable member_id for dashboard
        member_id = full_name.replace("/", "_").replace(":", "_")
        
        logger.info(f"  → Querying {full_name}...")
        
        # Get member-specific logger for detailed logging
        member_logger = get_member_logger(member_id, full_name)
        member_logger.info(f"Starting query for {full_name}")
        member_logger.debug(f"Provider: {provider}, Model: {model}")
        
        # Notify dashboard - starting query
        self._notify_dashboard(member_id, status="active", activity="Sending request...")
        
        if provider != "opencode":
            logger.error(f"Unknown provider: {provider}. Only 'opencode' is supported.")
            member_logger.error(f"Unknown provider: {provider}")
            self._notify_dashboard(member_id, status="error", error=f"Unknown provider: {provider}")
            return None
        
        # Convert messages to a single prompt for OpenCode
        prompt = self._messages_to_prompt(messages)
        
        # Notify dashboard - processing
        self._notify_dashboard(member_id, activity="Waiting for response...", api_calls_delta=1)
        
        response = await self.opencode_client.query_model(
            model=model,
            prompt=prompt,
            working_dir=working_dir,
            timeout=timeout
        )
        
        if response:
            response["full_name"] = full_name
            logger.success(f"  ✓ {full_name} completed")
            member_logger.success(f"Query completed successfully")
            member_logger.debug(f"Response length: {len(response.get('content', ''))} chars")
            self._notify_dashboard(member_id, status="completed", activity="Response received")
        else:
            logger.warning(f"  ✗ {full_name} failed")
            member_logger.error("Query failed - no response")
            self._notify_dashboard(member_id, status="error", error="No response received")
        return response
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert OpenAI-style messages to a single prompt string."""
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                prompt_parts.append(f"[System]: {content}")
            elif role == "user":
                prompt_parts.append(content)
            elif role == "assistant":
                prompt_parts.append(f"[Assistant]: {content}")
        
        return "\n\n".join(prompt_parts)
    
    async def query_members_parallel(
        self,
        members: List[Dict[str, str]],
        messages: List[Dict[str, str]],
        working_dirs: Optional[Dict[int, Path]] = None,
        timeout: float = 300.0
    ) -> List[Dict[str, Any]]:
        """
        Query multiple council members in parallel.
        
        Args:
            members: List of member dicts with 'provider', 'model', 'full_name'
            messages: List of message dicts to send to each member
            working_dirs: Optional dict mapping member index to working directory
            timeout: Request timeout
            
        Returns:
            List of response dicts (preserves order, includes None for failures)
        """
        # Notify dashboard - all members waiting
        if self.dashboard:
            for member in members:
                member_id = member["full_name"].replace("/", "_").replace(":", "_")
                self._notify_dashboard(member_id, status="waiting", activity="Queued...")
        
        tasks = []
        for i, member in enumerate(members):
            working_dir = working_dirs.get(i) if working_dirs else None
            tasks.append(
                self.query_member(
                    member=member,
                    messages=messages,
                    working_dir=working_dir,
                    timeout=timeout
                )
            )
        
        responses = await asyncio.gather(*tasks)
        
        # Build results list, filtering out None
        results = []
        for i, (member, response) in enumerate(zip(members, responses)):
            if response is not None:
                results.append({
                    "member_index": i,
                    "model": member["model"],
                    "provider": member["provider"],
                    "full_name": member["full_name"],
                    "response": response
                })
        
        return results
