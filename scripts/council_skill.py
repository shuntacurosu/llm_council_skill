"""
LLM Council - Claude Skill

A Claude Skill that orchestrates multiple LLMs to collectively analyze and respond to queries.
Uses git worktrees to manage individual council member work and anonymized peer review.
"""

import sys
import asyncio
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from logger import logger
from config import get_config
from council import CouncilOrchestrator
from storage import ConversationStorage


def run_council(query: str, use_worktrees: bool = False) -> Dict[str, Any]:
    """
    Run the LLM Council on a query.
    
    Args:
        query: The user's question or request
        use_worktrees: Whether to use git worktrees for code work
        
    Returns:
        Council results with all stages
    """
    # Get repository root (parent of scripts directory)
    repo_root = SCRIPTS_DIR.parent
    
    # Initialize orchestrator
    orchestrator = CouncilOrchestrator(repo_root)
    
    # Run the council
    results = asyncio.run(orchestrator.run_full_council(query, use_worktrees))
    
    # Generate conversation title
    logger.info("Generating conversation title...")
    title = asyncio.run(orchestrator.generate_conversation_title(query))
    logger.info(f"Title: {title}")
    
    # Save to conversation history
    config = get_config()
    storage = ConversationStorage(config.conversations_dir)
    
    # Create or update conversation with generated title
    conversation_id = str(uuid.uuid4())
    storage.add_session(conversation_id, query, results, title=title)
    
    return results


def format_results(results: Dict[str, Any]) -> str:
    """
    Format council results for display.
    
    Args:
        results: Council results from run_council
        
    Returns:
        Formatted string output
    """
    output = []
    
    output.append("=" * 80)
    output.append("LLM COUNCIL RESULTS")
    output.append("=" * 80)
    
    # Check for errors
    if 'error' in results:
        output.append(f"\nError: {results['error']}")
        output.append("=" * 80)
        return "\n".join(output)
    
    # Query
    output.append(f"\nQuery: {results.get('query', 'N/A')}")
    output.append("")
    
    # Stage 1: Individual Responses
    output.append("-" * 80)
    output.append("STAGE 1: Individual Council Member Responses")
    output.append("-" * 80)
    
    stage1 = results.get('stage1', [])
    for i, result in enumerate(stage1, 1):
        output.append(f"\n[{i}] {result.get('model', 'Unknown')}")
        output.append("-" * 40)
        output.append(result.get('response', 'No response'))
        
        if 'diff' in result:
            output.append("\nCode Changes:")
            output.append(result['diff'][:500] + "..." if len(result['diff']) > 500 else result['diff'])
        output.append("")
    
    # Stage 2: Peer Rankings
    output.append("-" * 80)
    output.append("STAGE 2: Peer Rankings")
    output.append("-" * 80)
    
    stage2 = results.get('stage2', [])
    for i, result in enumerate(stage2, 1):
        output.append(f"\n[{i}] {result.get('model', 'Unknown')}")
        output.append("-" * 40)
        
        parsed = result.get('parsed_ranking', [])
        if parsed:
            output.append("Ranking:")
            for rank, label in enumerate(parsed, 1):
                output.append(f"  {rank}. {label}")
        else:
            output.append("(Could not parse ranking)")
        output.append("")
    
    # Aggregate Rankings
    if 'aggregate_rankings' in results and results['aggregate_rankings']:
        output.append("-" * 80)
        output.append("AGGREGATE RANKINGS")
        output.append("-" * 80)
        
        label_to_model = results.get('label_to_model', {})
        for label, score in results['aggregate_rankings']:
            model = label_to_model.get(label, 'Unknown')
            output.append(f"{label}: {score:.2f} - {model}")
        output.append("")
    
    # Stage 3: Final Synthesis
    output.append("-" * 80)
    output.append("STAGE 3: Chairman's Final Synthesis")
    output.append("-" * 80)
    
    stage3 = results.get('stage3')
    if stage3:
        output.append(f"\nChairman Model: {stage3.get('model', 'Unknown')}")
        output.append("-" * 40)
        output.append(stage3.get('response', 'No synthesis available'))
    else:
        output.append("\nNo synthesis available (council did not return responses)")
    output.append("")
    
    output.append("=" * 80)
    
    return "\n".join(output)


def main():
    """Main entry point for the skill."""
    import argparse
    
    parser = argparse.ArgumentParser(description="LLM Council - Collective Intelligence Tool")
    parser.add_argument("query", nargs="?", help="Query to send to the council")
    parser.add_argument("--worktrees", action="store_true", help="Use git worktrees for code work")
    parser.add_argument("--list", action="store_true", help="List conversation history")
    parser.add_argument("--setup", action="store_true", help="Show setup instructions")
    
    args = parser.parse_args()
    
    if args.setup:
        logger.info("""
LLM Council Setup Instructions:

1. Create a .env file in the scripts/ directory:
   cd scripts
   cp .env.example .env

2. Edit .env and add your OpenRouter API key:
   OPENROUTER_API_KEY=sk-or-v1-your-api-key-here

3. Configure council members and chairman model in .env:
   COUNCIL_MODELS=openai/gpt-4,anthropic/claude-3-5-sonnet-20241022,...
   CHAIRMAN_MODEL=anthropic/claude-3-5-sonnet-20241022

4. Install dependencies:
   pip install httpx python-dotenv loguru

5. Run the council:
   python council_skill.py "Your query here"

For more information, see README.md
        """)
        return
    
    if args.list:
        config = get_config()
        storage = ConversationStorage(config.conversations_dir)
        conversations = storage.list_conversations()
        
        if not conversations:
            logger.info("No conversations found.")
        else:
            logger.info("\nConversation History:")
            logger.info("-" * 80)
            for conv in conversations:
                logger.info(f"ID: {conv['id']}")
                logger.info(f"Title: {conv['title']}")
                logger.info(f"Created: {conv['created_at']}")
                logger.info(f"Sessions: {conv['session_count']}")
                logger.info("-" * 80)
        return
    
    if not args.query:
        logger.error("Error: Please provide a query or use --setup for setup instructions")
        parser.print_help()
        return
    
    try:
        logger.info("Running LLM Council...")
        logger.info("This may take a minute as multiple models are queried in parallel.\n")
        
        results = run_council(args.query, use_worktrees=args.worktrees)
        
        formatted = format_results(results)
        print(formatted)
        
        # Log completion
        logger.success("Council session complete. Check scripts/logs/ for detailed logs.")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
