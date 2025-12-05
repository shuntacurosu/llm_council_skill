"""
LLM Council TUI Dashboard using Rich.

A real-time terminal dashboard to monitor council sessions.
Shows member status, current stage, logs, and statistics.
"""

import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from collections import deque

from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.style import Style


class MemberStatus(Enum):
    """Status of a council member."""
    IDLE = "idle"
    WAITING = "waiting"
    ACTIVE = "active"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class MemberState:
    """State of a council member."""
    name: str
    provider: str
    status: MemberStatus = MemberStatus.IDLE
    last_activity: str = ""
    activity_time: Optional[datetime] = None
    api_calls: int = 0
    tokens_used: int = 0
    error_message: Optional[str] = None


@dataclass 
class DashboardState:
    """Global dashboard state."""
    # Session info
    session_id: Optional[str] = None
    query: str = ""
    started_at: Optional[datetime] = None
    
    # Stage info
    current_stage: int = 0
    stage_name: str = "Idle"
    stage_progress: float = 0.0
    
    # Members
    members: Dict[str, MemberState] = field(default_factory=dict)
    
    # Logs (circular buffer - increased to show more context)
    log_messages: deque = field(default_factory=lambda: deque(maxlen=50))
    
    # Statistics
    total_api_calls: int = 0
    total_tokens: int = 0
    errors: int = 0
    
    # Countdown
    countdown_seconds: Optional[int] = None
    is_completed: bool = False
    
    def elapsed_time(self) -> str:
        """Get elapsed time as string."""
        if self.started_at is None:
            return "00:00"
        elapsed = datetime.now() - self.started_at
        minutes, seconds = divmod(int(elapsed.total_seconds()), 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"


class CouncilDashboard:
    """
    Rich-based TUI dashboard for LLM Council.
    
    Usage:
        dashboard = CouncilDashboard()
        dashboard.start()
        
        # Update state from council operations
        dashboard.set_stage(1, "Collecting Responses")
        dashboard.update_member("claude-3.5-sonnet", status=MemberStatus.ACTIVE)
        dashboard.add_log("Starting council session...")
        
        dashboard.stop()
    """
    
    def __init__(self):
        """Initialize the dashboard."""
        self.console = Console()
        self.state = DashboardState()
        self._live: Optional[Live] = None
        self._running = False
        self._lock = threading.Lock()
    
    def _get_status_icon(self, status: MemberStatus) -> str:
        """Get icon for member status."""
        icons = {
            MemberStatus.IDLE: "⚪",
            MemberStatus.WAITING: "⏳",
            MemberStatus.ACTIVE: "🟢",
            MemberStatus.COMPLETED: "✅",
            MemberStatus.ERROR: "❌",
        }
        return icons.get(status, "⚪")
    
    def _get_status_style(self, status: MemberStatus) -> Style:
        """Get style for member status."""
        styles = {
            MemberStatus.IDLE: Style(dim=True),
            MemberStatus.WAITING: Style(color="yellow"),
            MemberStatus.ACTIVE: Style(color="green", bold=True),
            MemberStatus.COMPLETED: Style(color="cyan"),
            MemberStatus.ERROR: Style(color="red", bold=True),
        }
        return styles.get(status, Style())
    
    def _create_stage_flow(self) -> Text:
        """Create a horizontal stage flow indicator."""
        stages = [
            (1, "Responses"),
            (2, "Rankings"),
            (3, "Synthesis"),
        ]
        
        flow = Text()
        
        for i, (stage_num, stage_name) in enumerate(stages):
            if i > 0:
                # Arrow connector
                if self.state.current_stage > stages[i-1][0]:
                    flow.append(" ━━▶ ", style="green")
                else:
                    flow.append(" ───▶ ", style="dim")
            
            # Stage box
            if self.state.is_completed and stage_num <= 3:
                # All completed
                flow.append(f"[{stage_num}] {stage_name}", style="green bold")
                flow.append(" ✓", style="green")
            elif stage_num == self.state.current_stage:
                # Active stage
                flow.append(f"[{stage_num}] {stage_name}", style="yellow bold on blue")
                flow.append(" ●", style="yellow bold")
            elif stage_num < self.state.current_stage:
                # Completed stage
                flow.append(f"[{stage_num}] {stage_name}", style="green")
                flow.append(" ✓", style="green")
            else:
                # Future stage
                flow.append(f"[{stage_num}] {stage_name}", style="dim")
        
        return flow
    
    def _create_header(self) -> Panel:
        """Create the header panel."""
        title = Text("🏛️  LLM Council Dashboard", style="bold white on blue")
        
        # Status line
        if self.state.started_at:
            status_text = Text()
            status_text.append(f"Session: ", style="dim")
            status_text.append(self.state.session_id or "N/A", style="cyan")
            status_text.append(" │ ", style="dim")
            status_text.append(f"Elapsed: ", style="dim")
            status_text.append(self.state.elapsed_time(), style="yellow")
            
            # Show countdown if completed
            if self.state.is_completed and self.state.countdown_seconds is not None:
                status_text.append(" │ ", style="dim")
                status_text.append(f"Closing in ", style="dim")
                status_text.append(f"{self.state.countdown_seconds}s", style="yellow bold")
            
            # Stage flow on separate line
            stage_flow = self._create_stage_flow()
            content = Group(title, status_text, stage_flow)
        else:
            status_text = Text("Waiting for session...", style="dim italic")
            content = Group(title, Text(""), status_text)
        
        return Panel(content, border_style="blue", padding=(0, 1))
    
    def _create_members_table(self) -> Panel:
        """Create the members status table."""
        table = Table(
            show_header=True,
            header_style="bold magenta",
            expand=True,
            box=None,
        )
        
        table.add_column("Status", width=3, justify="center")
        table.add_column("Member", min_width=25)
        table.add_column("Provider", width=10)
        table.add_column("Activity", min_width=20)
        table.add_column("Time", width=8, justify="right")
        table.add_column("API", width=5, justify="right")
        
        for member in self.state.members.values():
            icon = self._get_status_icon(member.status)
            style = self._get_status_style(member.status)
            
            # Calculate time since last activity
            if member.activity_time:
                delta = datetime.now() - member.activity_time
                time_str = f"{int(delta.total_seconds())}s"
            else:
                time_str = "-"
            
            activity = member.last_activity or "-"
            if len(activity) > 25:
                activity = activity[:22] + "..."
            
            table.add_row(
                icon,
                Text(member.name, style=style),
                member.provider,
                Text(activity, style=style),
                time_str,
                str(member.api_calls),
            )
        
        if not self.state.members:
            table.add_row("", Text("No members registered", style="dim italic"), "", "", "", "")
        
        return Panel(
            table,
            title="[bold]Council Members[/bold]",
            border_style="green",
            padding=(0, 1),
        )
    
    def _create_logs_panel(self) -> Panel:
        """Create the logs panel."""
        # Take a snapshot of logs - deque iteration is safe in CPython
        # Using list() creates an atomic copy
        log_snapshot = list(self.state.log_messages)
        
        # Show only the most recent logs that fit in the panel
        # Keep chronological order (oldest first, newest at bottom - like a terminal)
        recent_logs = log_snapshot[-15:]  # Last 15 entries
        
        log_text = Text()
        
        for i, (timestamp, level, message) in enumerate(recent_logs):
            if i > 0:
                log_text.append("\n")
            
            # Time
            log_text.append(timestamp.strftime("%H:%M:%S"), style="dim")
            log_text.append(" │ ", style="dim")
            
            # Level with color
            level_styles = {
                "INFO": "cyan",
                "SUCCESS": "green",
                "WARNING": "yellow", 
                "ERROR": "red bold",
                "DEBUG": "dim",
            }
            log_text.append(f"{level:7}", style=level_styles.get(level, "white"))
            log_text.append(" │ ", style="dim")
            
            # Message
            msg_style = "red" if level == "ERROR" else ""
            log_text.append(message[:80], style=msg_style)
        
        if not log_snapshot:
            log_text = Text("No logs yet...", style="dim italic")
        
        return Panel(
            log_text,
            title=f"[bold]Recent Logs ({len(log_snapshot)} total)[/bold]",
            border_style="yellow",
            padding=(0, 1),
        )
    
    def _create_stats_panel(self) -> Panel:
        """Create the statistics panel."""
        stats = Table.grid(padding=(0, 2))
        stats.add_column(justify="right", style="dim")
        stats.add_column(justify="left", style="bold")
        
        stats.add_row("API Calls:", str(self.state.total_api_calls))
        stats.add_row("Tokens:", f"{self.state.total_tokens:,}" if self.state.total_tokens else "-")
        stats.add_row("Errors:", Text(str(self.state.errors), style="red" if self.state.errors else "green"))
        stats.add_row("Members:", str(len(self.state.members)))
        stats.add_row("Log Count:", str(len(self.state.log_messages)))
        
        return Panel(
            stats,
            title="[bold]Statistics[/bold]",
            border_style="cyan",
            padding=(0, 1),
        )
    
    def _create_query_panel(self) -> Panel:
        """Create the query display panel."""
        query = self.state.query or "No query set"
        if len(query) > 100:
            query = query[:97] + "..."
        
        return Panel(
            Text(query, style="italic"),
            title="[bold]Current Query[/bold]",
            border_style="magenta",
            padding=(0, 1),
        )
    
    def _create_layout(self) -> Layout:
        """Create the dashboard layout."""
        layout = Layout()
        
        # Calculate dynamic sizes based on member count
        member_count = len(self.state.members)
        # Header row (1) + each member row (1) + padding (2 for borders)
        members_height = max(4, member_count + 3)
        # Stats panel: 6 rows + borders
        stats_height = 8
        # Query panel: 3 rows + borders  
        query_height = 5
        sidebar_height = stats_height + query_height
        
        # Main structure (header size increased for stage flow)
        layout.split_column(
            Layout(name="header", size=6),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        
        # Body split
        layout["body"].split_row(
            Layout(name="main", ratio=3),
            Layout(name="sidebar", ratio=1),
        )
        
        # Main area split - members table has fixed height based on member count
        layout["main"].split_column(
            Layout(name="members", size=members_height),
            Layout(name="logs"),  # Logs take remaining space
        )
        
        # Sidebar - fixed heights
        layout["sidebar"].split_column(
            Layout(name="stats", size=stats_height),
            Layout(name="query"),  # Query takes remaining space
        )
        
        # Populate
        layout["header"].update(self._create_header())
        layout["members"].update(self._create_members_table())
        layout["logs"].update(self._create_logs_panel())
        layout["stats"].update(self._create_stats_panel())
        layout["query"].update(self._create_query_panel())
        layout["footer"].update(
            Panel(
                Text("Press Ctrl+C to exit", justify="center", style="dim"),
                border_style="dim",
            )
        )
        
        return layout
    
    # =========================================================================
    # Public API for updating dashboard state
    # =========================================================================
    
    def start_session(self, session_id: str, query: str) -> None:
        """Start a new session."""
        with self._lock:
            self.state.session_id = session_id
            self.state.query = query
            self.state.started_at = datetime.now()
            self.state.current_stage = 0
            self.state.stage_name = "Starting"
            self.state.log_messages.clear()
            self.state.total_api_calls = 0
            self.state.total_tokens = 0
            self.state.errors = 0
            # Reset member statuses
            for member in self.state.members.values():
                member.status = MemberStatus.WAITING
                member.api_calls = 0
                member.last_activity = "Waiting..."
                member.activity_time = datetime.now()
    
    def set_stage(self, stage: int, name: str, progress: float = 0.0) -> None:
        """Set current stage."""
        with self._lock:
            self.state.current_stage = stage
            self.state.stage_name = name
            self.state.stage_progress = progress
    
    def register_member(self, member_id: str, name: str, provider: str) -> None:
        """Register a council member."""
        with self._lock:
            self.state.members[member_id] = MemberState(
                name=name,
                provider=provider,
                status=MemberStatus.IDLE,
            )
    
    def update_member(
        self,
        member_id: str,
        status: Optional[MemberStatus] = None,
        activity: Optional[str] = None,
        api_calls_delta: int = 0,
        tokens_delta: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """Update a member's state."""
        with self._lock:
            if member_id not in self.state.members:
                return
            
            member = self.state.members[member_id]
            
            if status is not None:
                member.status = status
            if activity is not None:
                member.last_activity = activity
                member.activity_time = datetime.now()
            if api_calls_delta:
                member.api_calls += api_calls_delta
                self.state.total_api_calls += api_calls_delta
            if tokens_delta:
                member.tokens_used += tokens_delta
                self.state.total_tokens += tokens_delta
            if error is not None:
                member.error_message = error
                member.status = MemberStatus.ERROR
                self.state.errors += 1
    
    def add_log(self, message: str, level: str = "INFO") -> None:
        """Add a log message. Thread-safe via atomic deque.append()."""
        # deque.append() is thread-safe in CPython, no lock needed
        self.state.log_messages.append((datetime.now(), level, message))
    
    def complete_session(self, success: bool = True) -> None:
        """Mark session as completed."""
        with self._lock:
            self.state.is_completed = True
            if success:
                self.state.stage_name = "✅ Completed"
                for member in self.state.members.values():
                    if member.status != MemberStatus.ERROR:
                        member.status = MemberStatus.COMPLETED
            else:
                self.state.stage_name = "❌ Failed"
    
    def set_countdown(self, seconds: int) -> None:
        """Set countdown seconds for display."""
        with self._lock:
            self.state.countdown_seconds = seconds
    
    def countdown_and_close(self, timeout_seconds: int) -> None:
        """
        Run countdown and close dashboard after timeout.
        
        Args:
            timeout_seconds: Number of seconds to countdown before closing
        """
        import time
        self.add_log(f"Closing in {timeout_seconds} seconds...", "INFO")
        for remaining in range(timeout_seconds, 0, -1):
            self.set_countdown(remaining)
            time.sleep(1)
        self.set_countdown(0)
    
    # =========================================================================
    # Display control
    # =========================================================================
    
    def start(self, refresh_rate: float = 10.0) -> None:
        """
        Start the live dashboard.
        
        Args:
            refresh_rate: Refresh rate in Hz (default 10 = 100ms)
        """
        self._running = True
        self._refresh_rate = refresh_rate
        
        # Create Live with auto_refresh=True so it updates automatically
        self._live = Live(
            self._create_layout(),
            console=self.console,
            refresh_per_second=refresh_rate,
            screen=True,
            auto_refresh=True,  # Enable automatic refresh
        )
        self._live.start()
        
        # Start background thread to update layout periodically
        import threading
        def _auto_update():
            while self._running and self._live:
                try:
                    self._live.update(self._create_layout())
                except Exception:
                    pass
                import time
                time.sleep(1.0 / refresh_rate)
        
        self._update_thread = threading.Thread(target=_auto_update, daemon=True)
        self._update_thread.start()
    
    def stop(self) -> None:
        """Stop the live dashboard."""
        self._running = False
        # Wait for update thread to finish
        if hasattr(self, '_update_thread') and self._update_thread.is_alive():
            self._update_thread.join(timeout=0.5)
        if self._live:
            self._live.stop()
            self._live = None
    
    def refresh(self) -> None:
        """Force refresh the display."""
        if self._live:
            self._live.update(self._create_layout())
    
    def is_running(self) -> bool:
        """Check if dashboard is running."""
        return self._running
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False


# =============================================================================
# Dashboard integration with logging
# =============================================================================

# Global dashboard instance for integration
_dashboard: Optional[CouncilDashboard] = None


def get_dashboard() -> Optional[CouncilDashboard]:
    """Get the global dashboard instance."""
    return _dashboard


def set_dashboard(dashboard: Optional[CouncilDashboard]) -> None:
    """Set the global dashboard instance."""
    global _dashboard
    _dashboard = dashboard


def create_dashboard_sink(dashboard: CouncilDashboard):
    """
    Create a loguru sink that forwards to the dashboard.
    
    Usage:
        from loguru import logger
        dashboard = CouncilDashboard()
        logger.add(create_dashboard_sink(dashboard))
    """
    def sink(message):
        try:
            record = message.record
            level = record["level"].name
            text = record["message"]
            # Add log immediately (thread-safe via _lock in add_log)
            dashboard.add_log(text, level)
        except Exception:
            # Silently ignore errors to prevent loguru from disabling this sink
            pass
    
    # Return sink with enqueue=False to ensure synchronous logging
    return sink


# =============================================================================
# Demo / Test
# =============================================================================

def demo():
    """Run a demo of the dashboard."""
    import random
    
    dashboard = CouncilDashboard()
    
    # Register some members
    members = [
        ("claude-3.5-sonnet", "Claude 3.5 Sonnet", "anthropic"),
        ("gpt-4o", "GPT-4o", "openai"),
        ("gemini-2.0-flash", "Gemini 2.0 Flash", "google"),
    ]
    
    for mid, name, provider in members:
        dashboard.register_member(mid, name, provider)
    
    with dashboard:
        # Simulate a session
        dashboard.start_session("demo-123", "What is the best programming language?")
        dashboard.add_log("Starting council session...")
        
        # Stage 1
        dashboard.set_stage(1, "Collecting Responses")
        dashboard.add_log("Stage 1: Collecting individual responses", "INFO")
        
        for mid, name, _ in members:
            dashboard.update_member(mid, status=MemberStatus.ACTIVE, activity="Generating response...")
            dashboard.add_log(f"Querying {name}...", "INFO")
            time.sleep(random.uniform(1, 2))
            dashboard.update_member(mid, status=MemberStatus.COMPLETED, activity="Response received", api_calls_delta=1)
            dashboard.add_log(f"{name} completed", "SUCCESS")
        
        # Stage 2
        dashboard.set_stage(2, "Peer Rankings")
        dashboard.add_log("Stage 2: Collecting peer rankings", "INFO")
        
        for mid, name, _ in members:
            dashboard.update_member(mid, status=MemberStatus.ACTIVE, activity="Ranking peers...")
            time.sleep(random.uniform(0.5, 1))
            dashboard.update_member(mid, status=MemberStatus.COMPLETED, activity="Rankings submitted", api_calls_delta=1)
        
        dashboard.add_log("All rankings collected", "SUCCESS")
        
        # Stage 3
        dashboard.set_stage(3, "Final Synthesis")
        dashboard.add_log("Stage 3: Chairman synthesizing...", "INFO")
        
        # Simulate one member (chairman) working
        dashboard.update_member("claude-3.5-sonnet", status=MemberStatus.ACTIVE, activity="Synthesizing final response...")
        time.sleep(2)
        dashboard.update_member("claude-3.5-sonnet", status=MemberStatus.COMPLETED, activity="Synthesis complete", api_calls_delta=1)
        
        dashboard.add_log("Final synthesis complete!", "SUCCESS")
        dashboard.complete_session(success=True)
        
        # Countdown before closing
        dashboard.countdown_and_close(5)


if __name__ == "__main__":
    demo()
