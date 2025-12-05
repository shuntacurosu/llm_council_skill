"""
LLM Council CLI

Command-line interface for the LLM Council.
Uses the API layer for all operations.
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from logger import logger
from api import CouncilAPI, MergeOptions, SessionProgress, SessionStatus


def format_results(results: Dict[str, Any]) -> str:
    """
    Format council results for CLI display.
    
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
    
    # Merge Result (if applicable)
    merge_result = results.get('merge_result')
    if merge_result:
        output.append("-" * 80)
        output.append("MERGE RESULT")
        output.append("-" * 80)
        
        status = merge_result.get('status', 'unknown')
        if status == 'merged':
            output.append(f"\n✓ Successfully merged changes from {merge_result.get('member', 'Unknown')}")
        elif status == 'applied':
            output.append(f"\n✓ Applied changes from {merge_result.get('member', 'Unknown')} (unstaged)")
            output.append("  Use 'git status' and 'git diff' to review")
            output.append("  Commit manually when ready")
        elif status == 'dry_run':
            output.append(f"\n(Dry run) {merge_result.get('members_with_diffs', 0)} members had code changes")
        elif status == 'cancelled':
            output.append("\n✗ Merge cancelled by user")
        elif status == 'no_changes':
            output.append("\n(No code changes to merge)")
        elif status == 'error':
            output.append(f"\n✗ Merge error: {merge_result.get('message', 'Unknown error')}")
        output.append("")
    
    output.append("=" * 80)
    
    return "\n".join(output)


def format_conversation_list(conversations: list) -> str:
    """Format conversation list for display."""
    if not conversations:
        return "No conversations found."
    
    lines = []
    lines.append("\n" + "=" * 80)
    lines.append("CONVERSATION HISTORY")
    lines.append("=" * 80)
    
    for conv in conversations:
        created = conv['created_at'][:10]
        sessions = conv['session_count']
        lines.append(f"\n[{conv['index']}] {conv['title']}")
        lines.append(f"    Created: {created} | Sessions: {sessions}")
    
    lines.append("\n" + "-" * 80)
    lines.append("Use --show N to view a conversation")
    lines.append("Use --continue N \"query\" to continue a conversation")
    lines.append("-" * 80 + "\n")
    
    return "\n".join(lines)


def format_conversation_detail(conversation: dict, index: int) -> str:
    """Format a single conversation for display."""
    lines = []
    lines.append("\n" + "=" * 80)
    lines.append(f"CONVERSATION: {conversation['title']}")
    lines.append(f"Created: {conversation['created_at']}")
    lines.append("=" * 80)
    
    for i, session in enumerate(conversation.get('sessions', []), 1):
        lines.append(f"\n--- Session {i} ({session['timestamp'][:10]}) ---")
        lines.append(f"\nQuery: {session['query']}")
        
        results = session.get('results', {})
        stage3 = results.get('stage3', {})
        if stage3:
            lines.append(f"\nChairman's Synthesis:")
            lines.append("-" * 40)
            lines.append(stage3.get('response', 'No response'))
        lines.append("")
    
    lines.append("=" * 80)
    lines.append(f"Use --continue {index} \"query\" to add to this conversation")
    lines.append("=" * 80 + "\n")
    
    return "\n".join(lines)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description="LLM Council - Collective Intelligence Tool"
    )
    parser.add_argument("query", nargs="?", help="Query to send to the council")
    parser.add_argument("--worktrees", action="store_true", 
                        help="Use git worktrees for code work")
    parser.add_argument("--dashboard", "-d", action="store_true",
                        help="Show live TUI dashboard during execution")
    parser.add_argument("--list", action="store_true", 
                        help="List conversation history")
    parser.add_argument("--show", type=int, metavar="N", 
                        help="Show conversation N (from --list)")
    parser.add_argument("--continue", dest="continue_conv", type=int, metavar="N",
                        help="Continue conversation N with a new query")
    parser.add_argument("--setup", action="store_true", 
                        help="Show setup instructions")
    
    # Merge options (require --worktrees)
    merge_group = parser.add_mutually_exclusive_group()
    merge_group.add_argument("--auto-merge", action="store_true",
                             help="Automatically merge the top-ranked proposal")
    merge_group.add_argument("--merge", type=int, metavar="N",
                             help="Merge proposal from member N (1-based index)")
    merge_group.add_argument("--dry-run", action="store_true",
                             help="Show diffs without merging (implies --worktrees)")
    parser.add_argument("--confirm", action="store_true",
                        help="Ask for confirmation before merging")
    parser.add_argument("--no-commit", action="store_true",
                        help="Apply changes without committing (leaves changes as unstaged)")
    
    return parser


def main():
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Initialize API (will be recreated with dashboard if needed)
    api = CouncilAPI()
    
    # Handle --setup
    if args.setup:
        print(api.get_setup_instructions())
        return
    
    # Handle --list
    if args.list:
        conversations = api.list_conversations()
        print(format_conversation_list(conversations))
        return
    
    # Handle --show
    if args.show:
        conversation = api.get_conversation(args.show)
        if conversation is None:
            logger.error(f"Conversation {args.show} not found. Use --list to see available conversations.")
            return
        print(format_conversation_detail(conversation, args.show))
        return
    
    # Handle --continue
    conversation_id = None
    if args.continue_conv:
        if not args.query:
            logger.error("Error: Please provide a query when using --continue")
            logger.info("Usage: python council_skill.py --continue N \"Your follow-up question\"")
            return
        
        conversation = api.get_conversation(args.continue_conv)
        if conversation is None:
            logger.error(f"Conversation {args.continue_conv} not found. Use --list to see available conversations.")
            return
        
        # Get conversation_id from storage
        from storage import ConversationStorage
        from config import get_config
        config = get_config()
        storage = ConversationStorage(config.conversations_dir)
        conversation_id = storage.get_conversation_id_by_index(args.continue_conv)
        
        logger.info(f"Continuing conversation: {conversation['title']}")
    
    # Require query for running council
    if not args.query:
        logger.error("Error: Please provide a query or use --setup for setup instructions")
        parser.print_help()
        return
    
    # Determine merge options
    use_worktrees = args.worktrees
    merge_options = MergeOptions()
    
    if args.auto_merge:
        merge_options.mode = "auto"
        use_worktrees = True
    elif args.merge:
        merge_options.mode = "manual"
        merge_options.member_index = args.merge
        use_worktrees = True
    elif args.dry_run:
        merge_options.mode = "dry-run"
        use_worktrees = True
    
    merge_options.confirm = args.confirm
    merge_options.no_commit = args.no_commit
    
    # Validate merge options
    if (args.auto_merge or args.merge or args.confirm) and not use_worktrees:
        logger.error("Error: Merge options require --worktrees or are implied by merge options")
        return
    
    # Run the council
    try:
        # Set up dashboard if requested
        dashboard = None
        dashboard_config = None
        if args.dashboard:
            try:
                from dashboard import CouncilDashboard, create_dashboard_sink
                from config import get_config
                # Use the same logger instance that other modules use
                from logger import logger as shared_logger, LOGS_DIR
                
                dashboard_config = get_config()
                dashboard = CouncilDashboard()
                
                # Remove ALL existing handlers (including those from logger.py setup)
                shared_logger.remove()
                
                # Re-add file handler only (no console to avoid dashboard interference)
                shared_logger.add(
                    LOGS_DIR / "council_{time:YYYY-MM-DD}.log",
                    level="DEBUG",
                    format="{time:HH:mm:ss} | {level:<8} | {message}",
                    rotation="1 day",
                    retention="7 days",
                    filter=lambda record: "member_log" not in record["extra"],
                    enqueue=False  # Synchronous logging
                )
                
                # Add dashboard as a log sink (synchronous to avoid delay)
                shared_logger.add(
                    create_dashboard_sink(dashboard),
                    level="INFO",
                    filter=lambda record: "member_log" not in record["extra"],
                    enqueue=False  # Ensure logs appear immediately
                )
            except ImportError:
                logger.warning("Dashboard requires 'rich' package. Install with: pip install rich")
                dashboard = None
        else:
            logger.info("Running LLM Council...")
            logger.info("This may take a minute as multiple models are queried in parallel.\n")
        
        # Initialize API with dashboard
        api = CouncilAPI()
        if dashboard:
            api.set_dashboard(dashboard)
            # Start session on dashboard
            session_id = f"session_{int(datetime.now().timestamp())}"
            dashboard.start_session(session_id, args.query)
        
        if dashboard:
            # Start with configured refresh rate
            refresh_rate = dashboard_config.dashboard_refresh_rate if dashboard_config else 10.0
            dashboard.start(refresh_rate=refresh_rate)
            try:
                results = api.run_council(
                    args.query,
                    use_worktrees=use_worktrees,
                    conversation_id=conversation_id,
                    merge_options=merge_options
                )
                dashboard.complete_session(success='error' not in results)
                
                # Countdown before closing dashboard
                timeout = dashboard_config.dashboard_timeout if dashboard_config else 5
                dashboard.countdown_and_close(timeout)
            finally:
                dashboard.stop()
        else:
            results = api.run_council(
                args.query,
                use_worktrees=use_worktrees,
                conversation_id=conversation_id,
                merge_options=merge_options
            )
        
        formatted = format_results(results)
        print(formatted)
        
        logger.success("Council session complete. Check scripts/data/logs/ for detailed logs.")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
