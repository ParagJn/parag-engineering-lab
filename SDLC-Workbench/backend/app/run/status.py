from __future__ import annotations

from ..config import Settings


def run_status(settings: Settings, active: int, watchers: int) -> dict:
    """Limits and live counts only. No project data, no paths, nothing that came from a model."""
    return {
        "max_concurrency": settings.run_max_concurrency,
        "max_cost_usd": settings.run_max_cost_usd or None,
        "max_seconds": settings.run_max_seconds or None,
        "active_runs": active,
        "event_watchers": watchers,
    }
