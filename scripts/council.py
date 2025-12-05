"""3-stage LLM Council orchestration with git worktree integration."""

import re
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

from logger import logger, get_stage_logger
from config import get_config
from unified_client import UnifiedLLMClient
from worktree_manager import WorktreeManager
from prompts.templates import (
    STAGE1_PROMPT,
    STAGE2_RANKING_PROMPT,
    STAGE3_SYNTHESIS_PROMPT,
    CODE_STAGE1_PROMPT,
    CODE_STAGE2_REVIEW_PROMPT,
    CODE_STAGE3_SYNTHESIS_PROMPT
)


class CouncilOrchestrator:
    """Orchestrates the 3-stage council process."""
    
    def __init__(self, repo_root: Path):
        """
        Initialize the council orchestrator.
        
        Args:
            repo_root: Root directory of the git repository
        """
        self.config = get_config()
        self.repo_root = repo_root
        
        # Use unified client that supports multiple providers
        self.client = UnifiedLLMClient(
            openrouter_api_key=self.config.openrouter_api_key,
            openrouter_api_url=self.config.openrouter_api_url,
            working_dir=repo_root
        )
        
        self.worktree_manager = WorktreeManager(
            repo_root=repo_root,
            worktrees_dir=self.config.worktrees_dir
        )
    
    async def stage1_collect_responses(
        self,
        user_query: str,
        use_worktrees: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Stage 1: Collect individual responses from all council models.
        
        Args:
            user_query: The user's question or request
            use_worktrees: Whether to create worktrees for code work
            
        Returns:
            List of dicts with 'model', 'response', and optionally 'worktree_path', 'diff'
        """
        members = self.config.get_council_members()
        
        # Prepare worktrees if needed (use index as key to handle duplicate models)
        worktree_paths = {}
        working_dirs = {}
        if use_worktrees:
            for i, member in enumerate(members):
                # Replace invalid characters for Windows directory names
                safe_model_name = member["full_name"].replace('/', '_').replace(':', '_')
                member_id = f"member_{i}_{safe_model_name}"
                try:
                    worktree_path = self.worktree_manager.create_worktree(member_id)
                    worktree_paths[i] = (member_id, worktree_path)
                    working_dirs[i] = worktree_path
                except Exception as e:
                    logger.error(f"Failed to create worktree for {member['full_name']}: {e}")
        
        # Prepare messages
        messages = [{"role": "user", "content": user_query}]
        
        # Query all members in parallel using unified client
        responses = await self.client.query_members_parallel(
            members=members,
            messages=messages,
            working_dirs=working_dirs if use_worktrees else None
        )
        
        # Format results
        stage1_results = []
        for item in responses:
            i = item['member_index']
            result = {
                "model": item['full_name'],
                "provider": item['provider'],
                "member_index": i,
                "response": item['response'].get('content', '')
            }
            
            # Add worktree information if applicable
            if i in worktree_paths:
                member_id, worktree_path = worktree_paths[i]
                result["member_id"] = member_id
                result["worktree_path"] = str(worktree_path)
                
                # Get diff if there are changes
                try:
                    diff = self.worktree_manager.get_worktree_diff(member_id)
                    if diff:
                        result["diff"] = diff
                except Exception as e:
                    logger.warning(f"Failed to get diff for {member_id}: {e}")
            
            stage1_results.append(result)
        
        return stage1_results
    
    async def stage2_collect_rankings(
        self,
        user_query: str,
        stage1_results: List[Dict[str, Any]],
        use_diffs: bool = False
    ) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """
        Stage 2: Each model ranks the anonymized responses.
        
        Args:
            user_query: The original user query
            stage1_results: Results from Stage 1
            use_diffs: Whether to use git diffs for ranking (for code work)
            
        Returns:
            Tuple of (rankings list, label_to_model mapping)
        """
        # Create anonymized labels for responses
        labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...
        
        # Create mapping from label to model name
        label_to_model = {
            f"Response {label}": result['model']
            for label, result in zip(labels, stage1_results)
        }
        
        # Build the content to review (responses or diffs)
        if use_diffs and any('diff' in r for r in stage1_results):
            # Use diffs for code review
            responses_text = "\n\n".join([
                f"Proposal {label}:\n{result.get('diff', result['response'])}"
                for label, result in zip(labels, stage1_results)
            ])
            prompt_template = CODE_STAGE2_REVIEW_PROMPT
            responses_text = responses_text.replace("Response", "Proposal")
        else:
            # Use text responses
            responses_text = "\n\n".join([
                f"Response {label}:\n{result['response']}"
                for label, result in zip(labels, stage1_results)
            ])
            prompt_template = STAGE2_RANKING_PROMPT
        
        # Build the ranking prompt
        ranking_prompt = prompt_template.format(
            user_query=user_query,
            responses_text=responses_text,
            changes_text=responses_text  # For code review template
        )
        
        messages = [{"role": "user", "content": ranking_prompt}]
        
        # Get rankings from all council members in parallel
        members = self.config.get_council_members()
        responses = await self.client.query_members_parallel(
            members=members,
            messages=messages
        )
        
        # Format results
        stage2_results = []
        for item in responses:
            full_text = item['response'].get('content', '')
            parsed = self._parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": item['full_name'],
                "provider": item['provider'],
                "ranking": full_text,
                "parsed_ranking": parsed
            })
        
        return stage2_results, label_to_model
    
    async def stage3_synthesize_final(
        self,
        user_query: str,
        stage1_results: List[Dict[str, Any]],
        stage2_results: List[Dict[str, Any]],
        use_code_synthesis: bool = False
    ) -> Dict[str, Any]:
        """
        Stage 3: Chairman synthesizes final response.
        
        Args:
            user_query: The original user query
            stage1_results: Individual model responses from Stage 1
            stage2_results: Rankings from Stage 2
            use_code_synthesis: Whether to synthesize code changes
            
        Returns:
            Dict with 'model' and 'response' keys
        """
        # Build comprehensive context for chairman
        stage1_text = "\n\n".join([
            f"Model: {result['model']}\nResponse: {result['response']}"
            for result in stage1_results
        ])
        
        stage2_text = "\n\n".join([
            f"Model: {result['model']}\nRanking: {result['ranking']}"
            for result in stage2_results
        ])
        
        # Choose appropriate prompt
        if use_code_synthesis:
            prompt_template = CODE_STAGE3_SYNTHESIS_PROMPT
        else:
            prompt_template = STAGE3_SYNTHESIS_PROMPT
        
        chairman_prompt = prompt_template.format(
            user_query=user_query,
            stage1_text=stage1_text,
            stage2_text=stage2_text
        )
        
        messages = [{"role": "user", "content": chairman_prompt}]
        
        # Query the chairman model
        chairman = self.config.get_chairman()
        response = await self.client.query_member(chairman, messages)
        
        if response is None:
            # Fallback if chairman fails
            return {
                "model": chairman['full_name'],
                "provider": chairman['provider'],
                "response": "Error: Unable to generate final synthesis."
            }
        
        return {
            "model": chairman['full_name'],
            "provider": chairman['provider'],
            "response": response.get('content', '')
        }
    
    def _parse_ranking_from_text(self, ranking_text: str) -> List[str]:
        """
        Parse the FINAL RANKING section from the model's response.
        
        Args:
            ranking_text: The full text response from the model
            
        Returns:
            List of response labels in ranked order
        """
        # Look for "FINAL RANKING:" section
        if "FINAL RANKING:" in ranking_text:
            # Extract everything after "FINAL RANKING:"
            parts = ranking_text.split("FINAL RANKING:")
            if len(parts) >= 2:
                ranking_section = parts[1]
                
                # Try to extract numbered list format (e.g., "1. Response A")
                numbered_matches = re.findall(
                    r'\d+\.\s*(?:Response|Proposal)\s+[A-Z]',
                    ranking_section
                )
                if numbered_matches:
                    # Extract just the "Response X" or "Proposal X" part
                    return [
                        re.search(r'(?:Response|Proposal)\s+[A-Z]', m).group()
                        for m in numbered_matches
                    ]
        
        # Fallback: couldn't parse ranking
        return []
    
    def calculate_aggregate_rankings(
        self,
        stage2_results: List[Dict[str, Any]],
        label_to_model: Dict[str, str]
    ) -> List[Tuple[str, float]]:
        """
        Calculate aggregate rankings from peer reviews.
        
        Args:
            stage2_results: Rankings from Stage 2
            label_to_model: Mapping from labels to model names
            
        Returns:
            List of (label, score) tuples sorted by score (higher is better)
        """
        # Count how many times each response appears at each rank
        rank_scores = {}
        
        for result in stage2_results:
            parsed = result.get('parsed_ranking', [])
            for rank, label in enumerate(parsed, start=1):
                if label not in rank_scores:
                    rank_scores[label] = []
                # Lower rank number = better, so invert the score
                score = len(parsed) - rank + 1
                rank_scores[label].append(score)
        
        # Calculate average scores
        avg_scores = {}
        for label, scores in rank_scores.items():
            avg_scores[label] = sum(scores) / len(scores) if scores else 0
        
        # Sort by score (descending)
        sorted_rankings = sorted(
            avg_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_rankings
    
    async def run_full_council(
        self,
        user_query: str,
        use_worktrees: bool = False
    ) -> Dict[str, Any]:
        """
        Run the complete 3-stage council process.
        
        Args:
            user_query: The user's question or request
            use_worktrees: Whether to use git worktrees for code work
            
        Returns:
            Complete council results with all stages
        """
        # Clean up any existing worktrees at the start of each session
        # This ensures a fresh start regardless of previous interruptions
        if use_worktrees:
            try:
                self.worktree_manager.prepare_fresh_worktrees()
            except Exception as e:
                logger.warning(f"Failed to prepare worktrees: {e}")
        
        # Stage 1: Collect individual responses
        stage1_logger = get_stage_logger("stage1")
        logger.info("Stage 1: Collecting individual responses...")
        stage1_logger.info("Starting Stage 1")
        stage1_results = await self.stage1_collect_responses(user_query, use_worktrees)
        stage1_logger.info(f"Stage 1 complete: {len(stage1_results)} responses")
        
        if not stage1_results:
            return {
                "error": "No responses received from council members",
                "stage1": [],
                "stage2": [],
                "stage3": None
            }
        
        # Stage 2: Collect peer rankings
        stage2_logger = get_stage_logger("stage2")
        logger.info("Stage 2: Collecting peer rankings...")
        stage2_logger.info("Starting Stage 2")
        stage2_results, label_to_model = await self.stage2_collect_rankings(
            user_query,
            stage1_results,
            use_diffs=use_worktrees
        )
        stage2_logger.info(f"Stage 2 complete: {len(stage2_results)} rankings")
        
        # Calculate aggregate rankings
        aggregate_rankings = self.calculate_aggregate_rankings(
            stage2_results,
            label_to_model
        )
        
        # Stage 3: Chairman synthesis
        stage3_logger = get_stage_logger("stage3")
        logger.info("Stage 3: Synthesizing final response...")
        stage3_logger.info("Starting Stage 3")
        stage3_result = await self.stage3_synthesize_final(
            user_query,
            stage1_results,
            stage2_results,
            use_code_synthesis=use_worktrees
        )
        stage3_logger.info("Stage 3 complete")
        
        # Cleanup worktrees after completion
        if use_worktrees:
            logger.info("Cleaning up worktrees...")
            try:
                self.worktree_manager.cleanup_all_worktrees()
                logger.success("  ✓ Cleanup complete")
            except Exception as e:
                logger.warning(f"  ✗ Failed to cleanup worktrees: {e}")
        
        return {
            "query": user_query,
            "stage1": stage1_results,
            "stage2": stage2_results,
            "stage3": stage3_result,
            "aggregate_rankings": aggregate_rankings,
            "label_to_model": label_to_model
        }
