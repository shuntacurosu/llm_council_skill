"""Logging configuration for LLM Council using loguru."""

import sys
from pathlib import Path
from loguru import logger

# Remove default handler
logger.remove()

# Get data directory (centralized for dashboard integration)
SCRIPTS_DIR = Path(__file__).parent
DATA_DIR = SCRIPTS_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
MEMBER_LOGS_DIR = LOGS_DIR / "members"
MEMBER_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Store member loggers
_member_loggers = {}


def setup_logger(
    console_level: str = "INFO",
    file_level: str = "DEBUG"
):
    """
    Set up loguru logger with console and file outputs.
    
    Args:
        console_level: Log level for console output
        file_level: Log level for file output
    """
    # Console handler - formatted for readability
    logger.add(
        sys.stderr,
        level=console_level,
        format="<level>{message}</level>",
        filter=lambda record: "member_log" not in record["extra"]
    )
    
    # Main log file - all council activity
    logger.add(
        LOGS_DIR / "council_{time:YYYY-MM-DD}.log",
        level=file_level,
        format="{time:HH:mm:ss} | {level:<8} | {message}",
        rotation="1 day",
        retention="7 days",
        filter=lambda record: "member_log" not in record["extra"]
    )


def get_member_logger(member_id: str, member_name: str):
    """
    Get a logger bound to a specific council member.
    
    Args:
        member_id: Unique identifier for the member (e.g., "member_0")
        member_name: Display name of the member
        
    Returns:
        Bound logger for the member
    """
    # Sanitize member_id for filename
    safe_id = member_id.replace('/', '_').replace(':', '_')
    
    # Create member-specific log file if not exists
    if safe_id not in _member_loggers:
        log_file = MEMBER_LOGS_DIR / f"{safe_id}.log"
        
        # Add handler for this member
        logger.add(
            log_file,
            level="DEBUG",
            format="{time:HH:mm:ss.SSS} | {level:<8} | {message}",
            filter=lambda record, sid=safe_id: record["extra"].get("member_id") == sid,
            rotation="1 MB",
            retention="3 days"
        )
        _member_loggers[safe_id] = True
    
    return logger.bind(member_id=safe_id, member_name=member_name, member_log=True)


def get_stage_logger(stage: str):
    """
    Get a logger bound to a specific stage.
    
    Args:
        stage: Stage name (e.g., "stage1", "stage2", "stage3")
        
    Returns:
        Bound logger for the stage
    """
    return logger.bind(stage=stage)


# Initialize with default settings
setup_logger()

# Export logger
__all__ = ["logger", "setup_logger", "get_member_logger", "get_stage_logger", "LOGS_DIR"]
