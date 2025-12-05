from config_loader import load_config


def get_setting(key: str, default=None):
    """Get a specific setting."""
    config = load_config()
    return config.get(key, default)
