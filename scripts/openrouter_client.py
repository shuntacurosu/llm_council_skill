"""OpenRouter API client for LLM Council."""

import httpx
import asyncio
from typing import List, Dict, Any, Optional

from logger import logger


class OpenRouterClient:
    """Client for interacting with OpenRouter API."""
    
    def __init__(self, api_key: str, api_url: str = "https://openrouter.ai/api/v1/chat/completions"):
        """
        Initialize the OpenRouter client.
        
        Args:
            api_key: OpenRouter API key
            api_url: OpenRouter API endpoint
        """
        self.api_key = api_key
        self.api_url = api_url
    
    async def query_model(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout: float = 120.0,
        system_prompt: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Query a single model via OpenRouter API.
        
        Args:
            model: OpenRouter model identifier (e.g., "openai/gpt-4")
            messages: List of message dicts with 'role' and 'content'
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt to prepend
            
        Returns:
            Response dict with 'content' and optional metadata, or None if failed
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Add system prompt if provided
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages
        
        payload = {
            "model": model,
            "messages": messages,
        }
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                message = data['choices'][0]['message']
                
                return {
                    'content': message.get('content', ''),
                    'model': model,
                    'reasoning_details': message.get('reasoning_details')
                }
        
        except httpx.TimeoutException:
            logger.error(f"Timeout querying model {model}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error querying model {model}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error querying model {model}: {e}")
            return None
    
    async def query_models_parallel(
        self,
        models: List[str],
        messages: List[Dict[str, str]],
        system_prompts: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Query multiple models in parallel.
        
        Args:
            models: List of OpenRouter model identifiers (can have duplicates)
            messages: List of message dicts to send to each model
            system_prompts: Optional dict mapping model to system prompt
            
        Returns:
            List of dicts with 'model' and response data (preserves order and duplicates)
        """
        # Create tasks for all models
        tasks = []
        for model in models:
            system_prompt = system_prompts.get(model) if system_prompts else None
            tasks.append(self.query_model(model, messages, system_prompt=system_prompt))
        
        # Wait for all to complete
        responses = await asyncio.gather(*tasks)
        
        # Return as list to preserve duplicates
        results = []
        for model, response in zip(models, responses):
            if response is not None:
                results.append({
                    "model": model,
                    "response": response
                })
        return results
