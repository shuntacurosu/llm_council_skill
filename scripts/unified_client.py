"""Unified LLM client that routes to appropriate providers."""

import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path

from openrouter_client import OpenRouterClient
from opencode_client import OpenCodeClient


class UnifiedLLMClient:
    """
    Unified client that routes requests to the appropriate LLM provider.
    
    Supports:
        - openrouter: OpenRouter API
        - opencode: OpenCode CLI
    """
    
    def __init__(
        self,
        openrouter_api_key: Optional[str] = None,
        openrouter_api_url: str = "https://openrouter.ai/api/v1/chat/completions",
        working_dir: Optional[Path] = None
    ):
        """
        Initialize the unified client.
        
        Args:
            openrouter_api_key: API key for OpenRouter
            openrouter_api_url: OpenRouter API endpoint
            working_dir: Working directory for OpenCode
        """
        self.openrouter_client = None
        if openrouter_api_key:
            self.openrouter_client = OpenRouterClient(
                api_key=openrouter_api_key,
                api_url=openrouter_api_url
            )
        
        self.opencode_client = OpenCodeClient(working_dir=working_dir)
    
    async def query_member(
        self,
        member: Dict[str, str],
        messages: List[Dict[str, str]],
        working_dir: Optional[Path] = None,
        timeout: float = 300.0
    ) -> Optional[Dict[str, Any]]:
        """
        Query a council member based on their provider.
        
        Args:
            member: Dict with 'provider', 'model', 'full_name' keys
            messages: List of message dicts (for OpenRouter format)
            working_dir: Working directory for OpenCode
            timeout: Request timeout
            
        Returns:
            Response dict with 'content' and 'model', or None if failed
        """
        provider = member["provider"]
        model = member["model"]
        full_name = member["full_name"]
        
        if provider == "openrouter":
            if not self.openrouter_client:
                print(f"OpenRouter client not initialized (no API key)")
                return None
            
            response = await self.openrouter_client.query_model(
                model=model,
                messages=messages,
                timeout=timeout
            )
            
            if response:
                response["full_name"] = full_name
            return response
            
        elif provider == "opencode":
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
            return response
            
        else:
            print(f"Unknown provider: {provider}")
            return None
    
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
