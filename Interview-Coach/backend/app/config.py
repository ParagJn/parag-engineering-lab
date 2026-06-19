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

    # Resolve sessions_dir relative to the backend directory
    sessions_dir = config["app"]["sessions_dir"]
    if not os.path.isabs(sessions_dir):
        base = Path(__file__).parent.parent
        config["app"]["sessions_dir"] = str((base / sessions_dir).resolve())

    return config
