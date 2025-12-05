"""Git worktree management for LLM Council members."""

import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import hashlib
import re

from logger import logger


class WorktreeManager:
    """Manages git worktrees for council members."""

    def __init__(self, repo_root: Path, worktrees_dir: Path):
        """
        Initialize the worktree manager.

        Args:
            repo_root: Root directory of the git repository
            worktrees_dir: Directory where worktrees will be created
        """
        self.repo_root = Path(repo_root)
        self.worktrees_dir = Path(worktrees_dir)
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

        # Verify we're in a git repository
        if not (self.repo_root / ".git").exists():
            raise ValueError(f"{self.repo_root} is not a git repository")

    def _run_git_command(
        self, args: List[str], cwd: Optional[Path] = None
    ) -> Tuple[int, str, str]:
        """
        Run a git command and return the result.

        Args:
            args: Git command arguments
            cwd: Working directory (defaults to repo_root)

        Returns:
            Tuple of (returncode, stdout, stderr)
        """
        if cwd is None:
            cwd = self.repo_root

        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return result.returncode, result.stdout, result.stderr

    def create_worktree(
        self, member_id: str, branch_name: Optional[str] = None
    ) -> Path:
        """
        Create a new worktree for a council member.

        Args:
            member_id: Unique identifier for the council member
            branch_name: Optional branch name (auto-generated if not provided)

        Returns:
            Path to the created worktree
        """
        # Generate safe branch name
        if branch_name is None:
            # Create a unique branch name based on member_id and timestamp
            safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", member_id)
            branch_name = f"council/{safe_id}"

        # Worktree path
        worktree_path = self.worktrees_dir / member_id

        # Remove existing worktree if it exists
        if worktree_path.exists():
            self.remove_worktree(member_id)

        # Create the worktree (create new branch from HEAD)
        returncode, stdout, stderr = self._run_git_command(
            ["worktree", "add", "-b", branch_name, str(worktree_path), "HEAD"]
        )

        if returncode != 0:
            # Branch might already exist, try without -b
            returncode, stdout, stderr = self._run_git_command(
                ["worktree", "add", str(worktree_path), branch_name]
            )

            if returncode != 0:
                raise RuntimeError(f"Failed to create worktree: {stderr}")

        return worktree_path

    def remove_worktree(self, member_id: str, force: bool = True):
        """
        Remove a worktree for a council member.

        Args:
            member_id: Unique identifier for the council member
            force: Force removal even if worktree has uncommitted changes
        """
        worktree_path = self.worktrees_dir / member_id

        if not worktree_path.exists():
            return

        # Remove the worktree
        args = ["worktree", "remove", str(worktree_path)]
        if force:
            args.append("--force")

        returncode, stdout, stderr = self._run_git_command(args)

        if returncode != 0 and worktree_path.exists():
            # If git command failed, manually remove the directory
            shutil.rmtree(worktree_path, ignore_errors=True)

    def get_worktree_diff(self, member_id: str) -> str:
        """
        Get the diff of changes in a worktree, including new (untracked) files.

        Args:
            member_id: Unique identifier for the council member

        Returns:
            Git diff output including new files
        """
        worktree_path = self.worktrees_dir / member_id

        if not worktree_path.exists():
            raise ValueError(f"Worktree for {member_id} does not exist")

        # First, add all untracked files to the index with --intent-to-add
        # This allows git diff to show new files without actually staging them
        self._run_git_command(["add", "-N", "."], cwd=worktree_path)

        # Get diff of all changes (staged, unstaged, and newly tracked files)
        returncode, stdout, stderr = self._run_git_command(
            ["diff", "HEAD"], cwd=worktree_path
        )

        if returncode != 0:
            # Try getting unstaged changes only
            returncode, stdout, stderr = self._run_git_command(
                ["diff"], cwd=worktree_path
            )

        return stdout

    def anonymize_diff(self, diff: str, member_id: str) -> str:
        """
        Anonymize a diff by removing identifying information.

        Args:
            diff: Git diff output
            member_id: Council member identifier to anonymize

        Returns:
            Anonymized diff
        """
        # Create a hash-based anonymous label
        hash_obj = hashlib.md5(member_id.encode())
        anon_label = f"Member_{hash_obj.hexdigest()[:8]}"

        # Replace member_id with anonymous label
        anonymized = diff.replace(member_id, anon_label)

        # Remove any author/committer information
        anonymized = re.sub(r"Author:.*\n", "", anonymized)
        anonymized = re.sub(r"Committer:.*\n", "", anonymized)
        anonymized = re.sub(r"Date:.*\n", "", anonymized)

        return anonymized

    def commit_changes(self, member_id: str, message: str) -> bool:
        """
        Commit all changes in a worktree.

        Args:
            member_id: Unique identifier for the council member
            message: Commit message

        Returns:
            True if changes were committed, False if nothing to commit
        """
        worktree_path = self.worktrees_dir / member_id

        if not worktree_path.exists():
            raise ValueError(f"Worktree for {member_id} does not exist")

        # Stage all changes
        returncode, stdout, stderr = self._run_git_command(
            ["add", "-A"], cwd=worktree_path
        )

        if returncode != 0:
            raise RuntimeError(f"Failed to stage changes: {stderr}")

        # Commit changes
        returncode, stdout, stderr = self._run_git_command(
            ["commit", "-m", message], cwd=worktree_path
        )

        if returncode != 0:
            # Check if there were no changes to commit
            if "nothing to commit" in stdout or "nothing to commit" in stderr:
                return False
            raise RuntimeError(f"Failed to commit changes: {stderr}")

        return True

    def apply_changes_to_main(self, member_id: str, strategy: str = "merge") -> bool:
        """
        Apply changes from a worktree to the main branch with commit.

        Args:
            member_id: Unique identifier for the council member
            strategy: How to apply changes ("merge" or "cherry-pick")

        Returns:
            True if successful
        """
        worktree_path = self.worktrees_dir / member_id

        if not worktree_path.exists():
            raise ValueError(f"Worktree for {member_id} does not exist")

        # Get the branch name from the worktree
        returncode, branch_name, stderr = self._run_git_command(
            ["rev-parse", "--abbrev-ref", "HEAD"], cwd=worktree_path
        )

        if returncode != 0:
            raise RuntimeError(f"Failed to get branch name: {stderr}")

        branch_name = branch_name.strip()

        # Switch to main branch in repo root
        returncode, stdout, stderr = self._run_git_command(["checkout", "main"])

        if returncode != 0:
            # Try master if main doesn't exist
            returncode, stdout, stderr = self._run_git_command(["checkout", "master"])
            if returncode != 0:
                raise RuntimeError(f"Failed to checkout main/master: {stderr}")

        # Apply changes
        if strategy == "merge":
            returncode, stdout, stderr = self._run_git_command(
                [
                    "merge",
                    "--no-ff",
                    branch_name,
                    "-m",
                    f"Merge council member {member_id}",
                ]
            )
        elif strategy == "cherry-pick":
            # Get the commit hash from the worktree branch
            returncode, commit_hash, stderr = self._run_git_command(
                ["rev-parse", branch_name]
            )
            if returncode == 0:
                commit_hash = commit_hash.strip()
                returncode, stdout, stderr = self._run_git_command(
                    ["cherry-pick", commit_hash]
                )
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        if returncode != 0:
            raise RuntimeError(f"Failed to apply changes: {stderr}")

        return True

    def apply_changes_without_commit(self, member_id: str) -> bool:
        """
        Apply changes from a worktree to the main working directory WITHOUT committing.

        This copies the file changes from the worktree to the main repository,
        leaving them as unstaged changes that can be reviewed and committed manually.
        Git-traceable: the changes will show up in `git status` and `git diff`.

        Args:
            member_id: Unique identifier for the council member

        Returns:
            True if successful
        """
        worktree_path = self.worktrees_dir / member_id

        if not worktree_path.exists():
            raise ValueError(f"Worktree for {member_id} does not exist")

        # Get the diff from worktree
        diff = self.get_worktree_diff(member_id)

        if not diff:
            logger.info(f"No changes to apply from {member_id}")
            return False

        # Apply the diff to main repository using git apply
        # This applies the patch without committing
        import subprocess

        # First try with --3way for better conflict handling
        result = subprocess.run(
            ["git", "apply", "--3way"],
            cwd=str(self.repo_root),
            input=diff,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        if result.returncode != 0:
            # Try without 3-way
            result = subprocess.run(
                ["git", "apply"],
                cwd=str(self.repo_root),
                input=diff,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            if result.returncode != 0:
                # If patch still fails, try copying files directly
                logger.warning(
                    f"git apply failed: {result.stderr}, trying direct file copy"
                )
                return self._copy_changed_files(member_id)

        logger.success(f"Applied changes from {member_id} (unstaged)")
        return True

    def merge_top_ranked_changes(
        self,
        stage1_results: List[Dict[str, Any]],
        aggregate_rankings: List[Tuple[str, float]],
        label_to_model: Dict[str, str],
        dry_run: bool = False,
        confirm: bool = False,
    ) -> Dict[str, Any]:
        """
        Merge changes from the top-ranked council member.

        Args:
            stage1_results: Results from Stage 1 with diff information
            aggregate_rankings: Sorted rankings from Stage 2
            label_to_model: Mapping from labels to model names
            dry_run: If True, show diffs without merging
            confirm: If True, ask for confirmation before merging

        Returns:
            Dict with merge status and details
        """
        # Find members with diffs
        members_with_diffs = [
            r for r in stage1_results if r.get("diff") and r.get("member_id")
        ]

        if not members_with_diffs:
            logger.info("No code changes to merge (no diffs found)")
            return {"status": "no_changes", "message": "No code changes to merge"}

        if dry_run:
            # Just show diffs, don't merge
            logger.info("\n" + "=" * 80)
            logger.info("DRY RUN - Showing diffs without merging")
            logger.info("=" * 80)

            for r in members_with_diffs:
                logger.info(
                    f"\n--- {r['model']} (member_index: {r['member_index']}) ---"
                )
                logger.info(r["diff"][:2000] if len(r["diff"]) > 2000 else r["diff"])

            return {"status": "dry_run", "members_with_diffs": len(members_with_diffs)}

        # Find top-ranked member with a diff
        if not aggregate_rankings:
            logger.error("Auto-merge failed: No valid rankings from Stage 2")
            return {
                "status": "error",
                "message": "Auto-merge requires valid rankings from Stage 2. All ranking parsers failed.",
            }

        # Get top-ranked label
        top_label = aggregate_rankings[0][0]  # e.g., "Response A"
        top_model = label_to_model.get(top_label)

        if not top_model:
            return {
                "status": "error",
                "message": f"Could not find model for {top_label}",
            }

        # Find the member with this model that has a diff
        matching = [r for r in members_with_diffs if r["model"] == top_model]

        if not matching:
            # Top-ranked member has no changes, try next ranked members
            logger.warning(f"Top-ranked {top_model} has no code changes")
            for label, score in aggregate_rankings[1:]:
                model = label_to_model.get(label)
                matching = [r for r in members_with_diffs if r["model"] == model]
                if matching:
                    logger.info(f"Using next ranked member with changes: {model}")
                    break

        if not matching:
            # No ranked member has changes - this is an error
            logger.error("No ranked member has code changes")
            return {
                "status": "error",
                "message": "None of the ranked members produced code changes",
            }

        target_member = matching[0]

        # Show diff and optionally confirm
        logger.info("\n" + "=" * 80)
        logger.info(f"MERGE TARGET: {target_member['model']}")
        logger.info("=" * 80)
        diff = target_member["diff"]
        logger.info(diff[:3000] if len(diff) > 3000 else diff)
        logger.info("=" * 80)

        if confirm:
            # Ask for confirmation
            print("\nMerge these changes? [y/N]: ", end="")
            response = input().strip().lower()
            if response != "y":
                logger.info("Merge cancelled by user")
                return {"status": "cancelled", "message": "Merge cancelled by user"}

        # Perform the merge
        member_id = target_member["member_id"]
        try:
            # First commit the changes in the worktree
            logger.info(f"Committing changes in worktree for {member_id}...")
            committed = self.commit_changes(
                member_id, f"Council proposal from {target_member['model']}"
            )

            if not committed:
                return {"status": "error", "message": "Nothing to commit"}

            # Apply changes to main
            logger.info("Applying changes to main branch...")
            self.apply_changes_to_main(member_id, strategy="merge")

            logger.success(
                f"  ✓ Successfully merged changes from {target_member['model']}"
            )

            return {
                "status": "merged",
                "member": target_member["model"],
                "member_id": member_id,
            }

        except Exception as e:
            logger.error(f"  ✗ Merge failed: {e}")
            return {"status": "error", "message": str(e)}

    def merge_member_changes(
        self,
        stage1_results: List[Dict[str, Any]],
        member_index: int,
        dry_run: bool = False,
        confirm: bool = False,
    ) -> Dict[str, Any]:
        """
        Merge changes from a specific council member by index.

        Args:
            stage1_results: Results from Stage 1 with diff information
            member_index: 1-based index of the member to merge
            dry_run: If True, show diffs without merging
            confirm: If True, ask for confirmation before merging

        Returns:
            Dict with merge status and details
        """
        # Find members with diffs
        members_with_diffs = [
            r for r in stage1_results if r.get("diff") and r.get("member_id")
        ]

        if not members_with_diffs:
            logger.info("No code changes to merge (no diffs found)")
            return {"status": "no_changes", "message": "No code changes to merge"}

        if dry_run:
            # Just show diffs, don't merge
            logger.info("\n" + "=" * 80)
            logger.info("DRY RUN - Showing diffs without merging")
            logger.info("=" * 80)

            for r in members_with_diffs:
                logger.info(
                    f"\n--- {r['model']} (member_index: {r['member_index']}) ---"
                )
                logger.info(r["diff"][:2000] if len(r["diff"]) > 2000 else r["diff"])

            return {"status": "dry_run", "members_with_diffs": len(members_with_diffs)}

        # Find member by index (1-based)
        target_idx = member_index - 1  # Convert to 0-based
        matching = [
            r for r in members_with_diffs if r.get("member_index") == target_idx
        ]

        if not matching:
            return {
                "status": "error",
                "message": f"Member {member_index} not found or has no changes",
            }

        target_member = matching[0]

        # Show diff and optionally confirm
        logger.info("\n" + "=" * 80)
        logger.info(f"MERGE TARGET: {target_member['model']} (Member {member_index})")
        logger.info("=" * 80)
        diff = target_member["diff"]
        logger.info(diff[:3000] if len(diff) > 3000 else diff)
        logger.info("=" * 80)

        if confirm:
            # Ask for confirmation
            print("\nMerge these changes? [y/N]: ", end="")
            response = input().strip().lower()
            if response != "y":
                logger.info("Merge cancelled by user")
                return {"status": "cancelled", "message": "Merge cancelled by user"}

        # Perform the merge
        member_id = target_member["member_id"]
        try:
            # First commit the changes in the worktree
            logger.info(f"Committing changes in worktree for {member_id}...")
            committed = self.commit_changes(
                member_id, f"Council proposal from {target_member['model']}"
            )

            if not committed:
                return {"status": "error", "message": "Nothing to commit"}

            # Apply changes to main
            logger.info("Applying changes to main branch...")
            self.apply_changes_to_main(member_id, strategy="merge")

            logger.success(
                f"  ✓ Successfully merged changes from {target_member['model']}"
            )

            return {
                "status": "merged",
                "member": target_member["model"],
                "member_id": member_id,
            }

        except Exception as e:
            logger.error(f"  ✗ Merge failed: {e}")
            return {"status": "error", "message": str(e)}

    def _copy_changed_files(self, member_id: str) -> bool:
        """
        Copy changed files from worktree to main repository.

        Fallback method when git apply fails.

        Args:
            member_id: Unique identifier for the council member

        Returns:
            True if successful
        """
        worktree_path = self.worktrees_dir / member_id

        # Get list of changed files
        returncode, stdout, stderr = self._run_git_command(
            ["diff", "--name-only", "HEAD"], cwd=worktree_path
        )

        if returncode != 0:
            raise RuntimeError(f"Failed to get changed files: {stderr}")

        changed_files = [f.strip() for f in stdout.strip().split("\n") if f.strip()]

        if not changed_files:
            return False

        # Copy each changed file
        for file_path in changed_files:
            src = worktree_path / file_path
            dst = self.repo_root / file_path

            if src.exists():
                # Ensure parent directory exists
                dst.parent.mkdir(parents=True, exist_ok=True)
                # Copy file content
                shutil.copy2(src, dst)
                logger.info(f"  Copied: {file_path}")
            else:
                # File was deleted
                if dst.exists():
                    dst.unlink()
                    logger.info(f"  Deleted: {file_path}")

        logger.success(f"Copied {len(changed_files)} changed file(s) from {member_id}")
        return True

    def cleanup_all_worktrees(self):
        """Remove all worktrees, associated branches, and clean up."""
        # List all worktrees
        returncode, stdout, stderr = self._run_git_command(["worktree", "list"])

        if returncode == 0:
            # Parse worktree list and remove non-main worktrees
            for line in stdout.split("\n"):
                if line and str(self.worktrees_dir) in line:
                    # Extract path
                    parts = line.split()
                    path = parts[0]
                    member_id = Path(path).name

                    try:
                        self.remove_worktree(member_id, force=True)
                    except Exception:
                        pass

        # Clean up any remaining directories
        if self.worktrees_dir.exists():
            for item in self.worktrees_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)

        # Prune worktree references
        self._run_git_command(["worktree", "prune"])

        # Delete all council/* branches
        returncode, stdout, stderr = self._run_git_command(
            ["branch", "--list", "council/*"]
        )
        if returncode == 0 and stdout.strip():
            for line in stdout.strip().split("\n"):
                branch = line.strip().lstrip("* ")
                if branch:
                    self._run_git_command(["branch", "-D", branch])

    def prepare_fresh_worktrees(self):
        """
        Clean up all existing worktrees and prepare for a fresh start.

        This should be called at the beginning of each council session
        to ensure a clean state regardless of previous interruptions.
        """
        logger.info("  Preparing fresh worktrees...")

        # Clean up all existing worktrees
        self.cleanup_all_worktrees()

        # Sync with parent tree (pull latest changes)
        self._sync_with_parent()

        logger.success("  ✓ Worktrees ready")

    def _sync_with_parent(self):
        """Sync the main repository with any upstream changes."""
        # Ensure we're on main/master
        returncode, current_branch, _ = self._run_git_command(
            ["rev-parse", "--abbrev-ref", "HEAD"]
        )

        if returncode == 0:
            current_branch = current_branch.strip()
            # If not on main/master, try to switch
            if current_branch not in ("main", "master"):
                self._run_git_command(["checkout", "main"])
                if (
                    self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])[
                        1
                    ].strip()
                    != "main"
                ):
                    self._run_git_command(["checkout", "master"])
