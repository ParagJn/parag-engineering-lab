import json
import os
from pathlib import Path
from functools import lru_cache


@lru_cache(maxsize=1)
def get_config() -> dict:
    """Load configuration from config.json, resolving paths relative to this file."""
    config_path = Path(__file__).parent.parent / "config.json"
    with open(config_path, "r") as f:
        config = json.load(f)

    config["app"].setdefault("settings_path", "../settings.json")
    config.setdefault(
        "direct_models",
        {
            "gpt": "gpt-4o-mini",
            "claude": "claude-3-5-sonnet-latest",
            "gemini": "gemini-1.5-pro",
        },
    )
    config.setdefault(
        "direct_api",
        {
            "max_tokens": 4096,
            "anthropic_version": "2023-06-01",
        },
    )

    # Resolve writable app paths relative to the backend directory
    base = Path(__file__).parent.parent
    for key in ("sessions_dir", "settings_path"):
        path_value = config["app"][key]
        if not os.path.isabs(path_value):
            config["app"][key] = str((base / path_value).resolve())

    return config
