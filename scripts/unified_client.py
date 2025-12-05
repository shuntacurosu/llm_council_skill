"""Unified LLM client - OpenCode CLI only."""

import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path

from logger import logger, get_member_logger
from opencode_client import OpenCodeClient


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
        working_dir: Optional[Path] = None
    ):
        """
        Initialize the unified client.
        
        Args:
            working_dir: Working directory for OpenCode
        """
        self.opencode_client = OpenCodeClient(working_dir=working_dir)
    
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
        
        logger.info(f"  → Querying {full_name}...")
        
        # Get member-specific logger for detailed logging
        member_id = f"member_{hash(full_name) % 1000}"
        member_logger = get_member_logger(member_id, full_name)
        member_logger.info(f"Starting query for {full_name}")
        member_logger.debug(f"Provider: {provider}, Model: {model}")
        
        if provider != "opencode":
            logger.error(f"Unknown provider: {provider}. Only 'opencode' is supported.")
            member_logger.error(f"Unknown provider: {provider}")
            return None
        
        # Convert messages to a single prompt for OpenCode
        prompt = self._messages_to_prompt(messages)
        
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
        else:
            logger.warning(f"  ✗ {full_name} failed")
            member_logger.error("Query failed - no response")
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
