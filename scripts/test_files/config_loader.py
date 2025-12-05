"""Simple configuration loader for testing scenario 3."""


def load_config():
    """Load configuration from environment."""
    import os

    return {
        "api_key": os.getenv("API_KEY", "default"),
        "debug": os.getenv("DEBUG", "false").lower() == "true",
        "timeout": int(os.getenv("TIMEOUT", "30")),
    }
