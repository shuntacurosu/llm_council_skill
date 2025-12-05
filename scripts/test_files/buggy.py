"""Test file for worktree merge scenario."""


def divide(a: float, b: float) -> float | None:
    """Divide a by b safely.

    Returns None if division by zero occurs.
    Other exceptions are propagated normally.
    """
    try:
        return a / b
    except ZeroDivisionError:
        return None


def calculate(x: int | float) -> int | float:
    """Simple calculation function."""
    return x * 2
