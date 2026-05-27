"""Configuration loading helpers for the mail application."""

from pathlib import Path

import yaml

_CONFIG = None


def _resolve_project_path(value):
    if isinstance(value, str) and (value.startswith("data/") or value.startswith("./")):
        return Path(value)
    return value


def load_config(config_path="config.yaml"):
    """Load YAML configuration and cache it as a dict."""
    global _CONFIG
    path = Path(config_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    for key in ("database_path", "mailbox_root", "spam_model_path"):
        if key in config:
            config[key] = _resolve_project_path(config[key])
    _CONFIG = config
    return config


def get_config():
    """Return cached config, loading config.yaml from cwd if needed."""
    global _CONFIG
    if _CONFIG is None:
        return load_config()
    return _CONFIG
