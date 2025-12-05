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
        
        # Use unified client (OpenCode CLI only)
        self.client = UnifiedLLMClient(
            working_dir=repo_root
        )
        
        self.worktree_manager = WorktreeManager(
            repo_root=repo_root,
            worktrees_dir=self.config.worktrees_dir
        )
    
    async def stage1_collect_responses(
        self,
        user_query: str,
        use_worktrees: bool = False,
        context_messages: List[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Stage 1: Collect individual responses from all council models.
        
        Args:
            user_query: The user's question or request
            use_worktrees: Whether to create worktrees for code work
            context_messages: Previous conversation messages for context
            
        Returns:
            List of dicts with 'model', 'response', and optionally 'worktree_path', 'diff'
        """
        if context_messages is None:
            context_messages = []
        
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
        
        # Prepare messages with context
        messages = context_messages.copy()
        messages.append({"role": "user", "content": user_query})
        
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
                
                # Extract code from response and write to worktree
                if result['response']:
                    self._extract_and_write_code(
                        response=result['response'],
                        worktree_path=worktree_path,
                        user_query=user_query
                    )
                
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
        use_worktrees: bool = False,
        context_messages: List[Dict[str, str]] = None,
        merge_mode: Optional[str] = None,
        merge_member: Optional[int] = None,
        confirm_merge: bool = False
    ) -> Dict[str, Any]:
        """
        Run the complete 3-stage council process.
        
        Args:
            user_query: The user's question or request
            use_worktrees: Whether to use git worktrees for code work
            context_messages: Previous conversation messages for context
            merge_mode: Merge mode - None, "auto", "manual", or "dry-run"
            merge_member: Member index to merge (1-based, for manual mode)
            confirm_merge: Whether to ask for confirmation before merging
            
        Returns:
            Complete council results with all stages
        """
        if context_messages is None:
            context_messages = []
        
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
        stage1_results = await self.stage1_collect_responses(
            user_query, 
            use_worktrees,
            context_messages=context_messages
        )
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
        
        # Handle merge if requested
        merge_result = None
        if use_worktrees and merge_mode:
            merge_result = self._handle_merge(
                stage1_results=stage1_results,
                aggregate_rankings=aggregate_rankings,
                label_to_model=label_to_model,
                merge_mode=merge_mode,
                merge_member=merge_member,
                confirm_merge=confirm_merge
            )
        
        # Cleanup worktrees after completion (unless dry-run keeps them for inspection)
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
            "label_to_model": label_to_model,
            "merge_result": merge_result
        }
    
    def _handle_merge(
        self,
        stage1_results: List[Dict[str, Any]],
        aggregate_rankings: List[Tuple[str, float]],
        label_to_model: Dict[str, str],
        merge_mode: str,
        merge_member: Optional[int] = None,
        confirm_merge: bool = False
    ) -> Dict[str, Any]:
        """
        Handle the merge of worktree changes based on the specified mode.
        
        Args:
            stage1_results: Results from Stage 1 with diff information
            aggregate_rankings: Sorted rankings from Stage 2
            label_to_model: Mapping from labels to model names
            merge_mode: "auto", "manual", or "dry-run"
            merge_member: Member index for manual mode (1-based)
            confirm_merge: Whether to ask for confirmation
            
        Returns:
            Dict with merge status and details
        """
        # Find members with diffs
        members_with_diffs = [
            r for r in stage1_results 
            if r.get('diff') and r.get('member_id')
        ]
        
        if not members_with_diffs:
            logger.info("No code changes to merge (no diffs found)")
            return {"status": "no_changes", "message": "No code changes to merge"}
        
        # Determine which member to merge
        target_member = None
        
        if merge_mode == "dry-run":
            # Just show diffs, don't merge
            logger.info("\n" + "=" * 80)
            logger.info("DRY RUN - Showing diffs without merging")
            logger.info("=" * 80)
            
            for r in members_with_diffs:
                logger.info(f"\n--- {r['model']} (member_index: {r['member_index']}) ---")
                logger.info(r['diff'][:2000] if len(r['diff']) > 2000 else r['diff'])
            
            return {"status": "dry_run", "members_with_diffs": len(members_with_diffs)}
        
        elif merge_mode == "manual":
            # Find member by index (1-based)
            if merge_member is None:
                return {"status": "error", "message": "No member index specified for manual merge"}
            
            target_idx = merge_member - 1  # Convert to 0-based
            matching = [r for r in members_with_diffs if r.get('member_index') == target_idx]
            
            if not matching:
                return {
                    "status": "error", 
                    "message": f"Member {merge_member} not found or has no changes"
                }
            target_member = matching[0]
            
        elif merge_mode == "auto":
            # Find top-ranked member with a diff
            if not aggregate_rankings:
                return {"status": "error", "message": "No rankings available"}
            
            # Get top-ranked label
            top_label = aggregate_rankings[0][0]  # e.g., "Response A"
            top_model = label_to_model.get(top_label)
            
            if not top_model:
                return {"status": "error", "message": f"Could not find model for {top_label}"}
            
            # Find the member with this model that has a diff
            matching = [r for r in members_with_diffs if r['model'] == top_model]
            
            if not matching:
                # Top-ranked member has no changes, try next
                logger.warning(f"Top-ranked {top_model} has no code changes")
                for label, score in aggregate_rankings[1:]:
                    model = label_to_model.get(label)
                    matching = [r for r in members_with_diffs if r['model'] == model]
                    if matching:
                        logger.info(f"Using next ranked member with changes: {model}")
                        break
            
            if not matching:
                return {"status": "error", "message": "No ranked member has code changes"}
            
            target_member = matching[0]
        
        if target_member is None:
            return {"status": "error", "message": "No target member found for merge"}
        
        # Show diff and optionally confirm
        logger.info("\n" + "=" * 80)
        logger.info(f"MERGE TARGET: {target_member['model']}")
        logger.info("=" * 80)
        diff = target_member['diff']
        logger.info(diff[:3000] if len(diff) > 3000 else diff)
        logger.info("=" * 80)
        
        if confirm_merge:
            # Ask for confirmation
            print("\nMerge these changes? [y/N]: ", end="")
            response = input().strip().lower()
            if response != 'y':
                logger.info("Merge cancelled by user")
                return {"status": "cancelled", "message": "Merge cancelled by user"}
        
        # Perform the merge
        member_id = target_member['member_id']
        try:
            # First commit the changes in the worktree
            logger.info(f"Committing changes in worktree for {member_id}...")
            committed = self.worktree_manager.commit_changes(
                member_id, 
                f"Council proposal from {target_member['model']}"
            )
            
            if not committed:
                return {"status": "error", "message": "Nothing to commit"}
            
            # Apply changes to main
            logger.info("Applying changes to main branch...")
            self.worktree_manager.apply_changes_to_main(member_id, strategy="merge")
            
            logger.success(f"  ✓ Successfully merged changes from {target_member['model']}")
            
            return {
                "status": "merged",
                "member": target_member['model'],
                "member_id": member_id
            }
            
        except Exception as e:
            logger.error(f"  ✗ Merge failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def generate_conversation_title(self, user_query: str) -> str:
        """
        Generate a short title for a conversation based on the first user message.
        
        Args:
            user_query: The first user message
            
        Returns:
            A short title (3-5 words)
        """
        title_prompt = """Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.
Respond with ONLY the title, nothing else.

Question: {query}

Title:""".format(query=user_query)
        
        messages = [{"role": "user", "content": title_prompt}]
        
        # Use the configured title model
        title_model = self.config.get_title_model()
        
        try:
            response = await self.client.query_member(title_model, messages)
            
            if response is None:
                return "New Conversation"
            
            title = response.get('content', 'New Conversation').strip()
            
            # Clean up the title - remove quotes, limit length
            title = title.strip('"\'')
            
            # Remove any leading/trailing punctuation
            title = title.strip('.,!?:;')
            
            # Truncate if too long
            if len(title) > 50:
                title = title[:47] + "..."
            
            return title if title else "New Conversation"
            
        except Exception as e:
            logger.warning(f"Failed to generate title: {e}")
            return "New Conversation"
