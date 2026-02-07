import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _load_json_config() -> dict[str, Any]:
    config_path = os.getenv("APP_CONFIG_PATH", "app/config.json")
    absolute_path = Path(config_path)
    if not absolute_path.is_absolute():
        absolute_path = Path.cwd() / absolute_path
    with absolute_path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


CONFIG = _load_json_config()

PORT = int(os.getenv("PORT", str(CONFIG["server"]["port"])))
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

REQUEST_TIMEOUT_SECONDS = int(CONFIG["llm"]["request_timeout_seconds"])

GEMINI = CONFIG["llm"]["gemini"]
CLAUDE = CONFIG["llm"]["claude"]
