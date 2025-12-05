"""OpenCode CLI client for LLM Council."""

import subprocess
import asyncio
import shutil
import os
import tempfile
from typing import Optional, Dict, Any
from pathlib import Path

from logger import logger

# Maximum command line length on Windows (conservative estimate)
MAX_CMD_LENGTH = 6000


class OpenCodeClient:
    """Client for interacting with OpenCode CLI."""
    
    def __init__(self, working_dir: Optional[Path] = None):
        """
        Initialize the OpenCode client.
        
        Args:
            working_dir: Working directory for opencode commands
        """
        self.working_dir = working_dir or Path.cwd()
        
        # Find opencode executable
        self.opencode_path = self._find_opencode()
    
    def _find_opencode(self) -> str:
        """Find the opencode executable path."""
        # Try to find in PATH
        opencode_path = shutil.which("opencode")
        if opencode_path:
            return opencode_path
        
        # Common installation paths on Windows
        if os.name == 'nt':
            npm_path = Path(os.environ.get('APPDATA', '')) / 'npm' / 'opencode.cmd'
            if npm_path.exists():
                return str(npm_path)
        
        # Default to hoping it's in PATH
        return "opencode"
    
    async def query_model(
        self,
        model: str,
        prompt: str,
        timeout: float = 300.0,
        working_dir: Optional[Path] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Query a model via OpenCode CLI.
        
        Args:
            model: Model identifier in provider/model format (e.g., "anthropic/claude-3")
            prompt: The prompt to send
            timeout: Request timeout in seconds
            working_dir: Working directory for the command
            
        Returns:
            Response dict with 'content', or None if failed
        """
        cwd = working_dir or self.working_dir
        
        # Check if prompt is too long for command line
        # If so, write to a temp file and use --file flag
        use_temp_file = len(prompt) > MAX_CMD_LENGTH
        temp_file_path = None
        
        try:
            if use_temp_file:
                # Create temp file with prompt
                fd, temp_file_path = tempfile.mkstemp(suffix='.txt', prefix='opencode_prompt_')
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(prompt)
                
                # Build command with file input
                # Use a simple instruction to read the file
                cmd = [
                    self.opencode_path, "run",
                    "-m", model,
                    "-f", temp_file_path,
                    "Execute the task described in the attached file."
                ]
            else:
                # Build the opencode run command
                cmd = [
                    self.opencode_path, "run",
                    "-m", model,
                    prompt
                ]
        
            if use_temp_file:
                # Use exec for temp file approach (no shell quoting issues)
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(cwd)
                )
            elif os.name == 'nt' and self.opencode_path.endswith('.cmd'):
                # On Windows, run through shell for .cmd files
                process = await asyncio.create_subprocess_shell(
                    f'"{self.opencode_path}" run -m {model} "{prompt}"',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(cwd)
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(cwd)
                )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='replace')
                logger.error(f"OpenCode error for model {model}: {error_msg[:200]}")
                return None
            
            content = stdout.decode('utf-8', errors='replace')
            
            return {
                'content': content.strip(),
                'model': model
            }
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout querying model {model} via OpenCode")
            return None
        except FileNotFoundError:
            logger.error(f"OpenCode CLI not found. Please install opencode: npm install -g opencode-ai")
            return None
        except Exception as e:
            logger.error(f"Error querying model {model} via OpenCode: {e}")
            return None
        finally:
            # Clean up temp file if used
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
    
    async def query_model_in_worktree(
        self,
        model: str,
        prompt: str,
        worktree_path: Path,
        timeout: float = 300.0
    ) -> Optional[Dict[str, Any]]:
        """
        Query a model via OpenCode CLI within a specific worktree.
        
        This allows OpenCode to make changes in an isolated worktree.
        
        Args:
            model: Model identifier
            prompt: The prompt to send
            worktree_path: Path to the git worktree
            timeout: Request timeout in seconds
            
        Returns:
            Response dict with 'content', or None if failed
        """
        return await self.query_model(
            model=model,
            prompt=prompt,
            timeout=timeout,
            working_dir=worktree_path
        )
