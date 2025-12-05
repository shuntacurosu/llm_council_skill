"""
LLM Council - Claude Skill

A Claude Skill that orchestrates multiple LLMs to collectively analyze and respond to queries.
Uses git worktrees to manage individual council member work and anonymized peer review.

This module provides backward compatibility. The implementation has been refactored into:
- api.py: High-level API for programmatic access
- cli.py: Command-line interface

For programmatic use, import from api.py:
    from api import CouncilAPI, MergeOptions
    
    api = CouncilAPI()
    results = api.run_council("Your query here")
"""

import sys
from pathlib import Path

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

# Re-export main components for backward compatibility
from api import CouncilAPI, MergeOptions, SessionProgress, SessionStatus, get_api
from cli import format_results, main

# Legacy function for backward compatibility
def run_council(*args, **kwargs):
    """
    Run the LLM Council on a query.
    
    Deprecated: Use CouncilAPI.run_council() instead.
    """
    api = CouncilAPI()
    
    # Convert old-style arguments to new MergeOptions
    merge_mode = kwargs.pop('merge_mode', None)
    merge_member = kwargs.pop('merge_member', None)
    confirm_merge = kwargs.pop('confirm_merge', False)
    no_commit = kwargs.pop('no_commit', False)
    
    merge_options = MergeOptions(
        mode=merge_mode,
        member_index=merge_member,
        confirm=confirm_merge,
        no_commit=no_commit
    )
    
    return api.run_council(
        *args,
        merge_options=merge_options,
        **kwargs
    )


if __name__ == "__main__":
    main()
