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


def run_council(
    query: str, 
    use_worktrees: bool = False,
    conversation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run the LLM Council on a query.
    
    Args:
        query: The user's question or request
        use_worktrees: Whether to use git worktrees for code work
        conversation_id: Optional existing conversation ID to continue
        
    Returns:
        Council results with all stages
    """
    # Get repository root (parent of scripts directory)
    repo_root = SCRIPTS_DIR.parent
    
    # Initialize orchestrator
    orchestrator = CouncilOrchestrator(repo_root)
    
    # Get conversation history if continuing
    config = get_config()
    storage = ConversationStorage(config.conversations_dir)
    
    context_messages = []
    if conversation_id:
        context_messages = storage.get_conversation_history(conversation_id)
        if context_messages:
            logger.info(f"Continuing conversation with {len(context_messages)} previous messages")
    
    # Run the council (with context if available)
    results = asyncio.run(orchestrator.run_full_council(
        query, 
        use_worktrees,
        context_messages=context_messages
    ))
    
    # Generate title only for new conversations
    if conversation_id is None:
        logger.info("Generating conversation title...")
        title = asyncio.run(orchestrator.generate_conversation_title(query))
        logger.info(f"Title: {title}")
        conversation_id = str(uuid.uuid4())
        storage.add_session(conversation_id, query, results, title=title)
    else:
        # Add session to existing conversation (no title update)
        storage.add_session(conversation_id, query, results)
    
    # Store conversation_id in results for reference
    results["conversation_id"] = conversation_id
    
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
    parser.add_argument("--show", type=int, metavar="N", help="Show conversation N (from --list)")
    parser.add_argument("--continue", dest="continue_conv", type=int, metavar="N", 
                        help="Continue conversation N with a new query")
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

6. Continue a conversation:
   python council_skill.py --list
   python council_skill.py --continue 1 "Follow-up question"

For more information, see README.md
        """)
        return
    
    config = get_config()
    storage = ConversationStorage(config.conversations_dir)
    
    if args.list:
        conversations = storage.list_conversations()
        
        if not conversations:
            logger.info("No conversations found.")
        else:
            print("\n" + "=" * 80)
            print("CONVERSATION HISTORY")
            print("=" * 80)
            for conv in conversations:
                # Format date nicely
                created = conv['created_at'][:10]  # Just the date part
                sessions = conv['session_count']
                print(f"\n[{conv['index']}] {conv['title']}")
                print(f"    Created: {created} | Sessions: {sessions}")
            print("\n" + "-" * 80)
            print("Use --show N to view a conversation")
            print("Use --continue N \"query\" to continue a conversation")
            print("-" * 80 + "\n")
        return
    
    if args.show:
        conversation = storage.get_conversation_by_index(args.show)
        if conversation is None:
            logger.error(f"Conversation {args.show} not found. Use --list to see available conversations.")
            return
        
        print("\n" + "=" * 80)
        print(f"CONVERSATION: {conversation['title']}")
        print(f"Created: {conversation['created_at']}")
        print("=" * 80)
        
        for i, session in enumerate(conversation.get('sessions', []), 1):
            print(f"\n--- Session {i} ({session['timestamp'][:10]}) ---")
            print(f"\nQuery: {session['query']}")
            
            results = session.get('results', {})
            stage3 = results.get('stage3', {})
            if stage3:
                print(f"\nChairman's Synthesis:")
                print("-" * 40)
                print(stage3.get('response', 'No response'))
            print("")
        
        print("=" * 80)
        print(f"Use --continue {args.show} \"query\" to add to this conversation")
        print("=" * 80 + "\n")
        return
    
    # Handle --continue with query
    if args.continue_conv:
        if not args.query:
            logger.error("Error: Please provide a query when using --continue")
            logger.info("Usage: python council_skill.py --continue N \"Your follow-up question\"")
            return
        
        conversation_id = storage.get_conversation_id_by_index(args.continue_conv)
        if conversation_id is None:
            logger.error(f"Conversation {args.continue_conv} not found. Use --list to see available conversations.")
            return
        
        conversation = storage.get_conversation(conversation_id)
        logger.info(f"Continuing conversation: {conversation['title']}")
    else:
        conversation_id = None
    
    if not args.query:
        logger.error("Error: Please provide a query or use --setup for setup instructions")
        parser.print_help()
        return
    
    try:
        logger.info("Running LLM Council...")
        logger.info("This may take a minute as multiple models are queried in parallel.\n")
        
        results = run_council(
            args.query, 
            use_worktrees=args.worktrees,
            conversation_id=conversation_id
        )
        
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
