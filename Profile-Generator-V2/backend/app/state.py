from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class JobState:
    job_id: str
    status: str = "queued"
    progress: int = 0
    step_message: str = "Queued"
    error: str | None = None
    result: dict[str, Any] | None = None


BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

JOBS: dict[str, JobState] = {}
