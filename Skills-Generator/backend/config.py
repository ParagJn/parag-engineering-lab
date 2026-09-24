"""
Application configuration.

All settings come from the project-root .env file. IBM ICA is the only
model provider.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(dotenv_path=BASE_DIR / ".env")


class Config:
    """Application configuration."""

    # Paths
    BASE_DIR = BASE_DIR
    SKILLS_DIR = BASE_DIR / "skills"
    ARCHIVE_DIR = SKILLS_DIR / ".archive"
    METADATA_FILE = SKILLS_DIR / ".metadata.json"

    # Platform-specific skill folders that generated skills are synced into
    PLATFORM_SKILL_DIRS = {
        "anthropic": BASE_DIR / ".claude" / "skills",
        "gemini": BASE_DIR / ".gemini" / "skills",
    }

    # Personal Claude Code skills folder ("Install to ~/.claude/skills")
    PERSONAL_SKILLS_DIR = Path(
        os.getenv("CLAUDE_PERSONAL_SKILLS_DIR", str(Path.home() / ".claude" / "skills"))
    ).expanduser()

    # IBM ICA Model Configuration
    IBM_ICA_API_KEY = os.getenv("IBM_ICA_API_KEY", "")
    IBM_ICA_ENDPOINT = os.getenv("IBM_ICA_ENDPOINT", "")
    IBM_ICA_MODEL_ID = os.getenv("IBM_ICA_MODEL_ID", "claude-opus-5-5")
    IBM_ICA_GEMINI_MODEL_ID = os.getenv("IBM_ICA_GEMINI_MODEL_ID", "gemini-3.7-flash")
    IBM_ICA_INSECURE_TLS = os.getenv("IBM_ICA_INSECURE_TLS", "false").lower() in ("true", "1", "yes")

    # Target skill platform -> ICA model_id used to generate it
    MODEL_CHOICES = {
        "anthropic": IBM_ICA_MODEL_ID,
        "gemini": IBM_ICA_GEMINI_MODEL_ID,
        "chatgpt": IBM_ICA_MODEL_ID,
    }

    # Model settings
    MODEL_TIMEOUT = int(os.getenv("MODEL_TIMEOUT", "300"))
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "8000"))
    # Writing a whole skill bundle (SKILL.md + references + scripts) needs more room
    GENERATION_MAX_TOKENS = int(os.getenv("GENERATION_MAX_TOKENS", "16000"))
    # Blueprint -> write -> validate -> repair rounds (only errors trigger a repair)
    MAX_REPAIR_ROUNDS = int(os.getenv("MAX_REPAIR_ROUNDS", "2"))

    # API settings
    API_PREFIX = "/api"
    CORS_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        errors = []

        if not cls.IBM_ICA_API_KEY:
            errors.append("IBM_ICA_API_KEY is required")
        if not cls.IBM_ICA_ENDPOINT:
            errors.append("IBM_ICA_ENDPOINT is required")

        if errors:
            raise ValueError(
                f"Configuration errors: {', '.join(errors)} (set them in {cls.BASE_DIR / '.env'})"
            )

    @classmethod
    def ensure_directories(cls):
        """Ensure required directories exist."""
        cls.SKILLS_DIR.mkdir(exist_ok=True)
        cls.ARCHIVE_DIR.mkdir(exist_ok=True)


config = Config()
