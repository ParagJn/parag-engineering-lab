from __future__ import annotations

from ..config import Settings
from .families import SLOT_NAMES, fallback_env, model_env
from .recordings import RecordingStore, recordings_mode
from .routing import Routing


def recordings_status(settings: Settings, store: RecordingStore | None) -> dict:
    """File names and reasons only. Never a path and never a recording's content."""
    return {
        "mode": recordings_mode(settings),
        "set": settings.replay_set,
        "count": len(store) if store is not None else 0,
        "problems": [f"{p.file}: {p.reason}" for p in store.problems] if store is not None else [],
    }


def gateway_status(
    settings: Settings, routing: Routing, provider_label: str, recordings: RecordingStore | None = None
) -> dict:
    """What the page shows. Names environment variables in problems, never their values."""
    slots = settings.slots
    problems: list[str] = []

    if settings.app_mode == "replay":
        if settings.record_live_calls:
            problems.append("RECORD_LIVE_CALLS is on but APP_MODE is replay, so nothing is being recorded")
        # An empty set is fine: a fresh checkout has none until one is recorded.
        for item in (recordings.problems if recordings is not None else []):
            problems.append(f"recording {item.file} is unusable: {item.reason}")

    seen: dict[str, str] = {}
    for name in SLOT_NAMES:
        model = slots[name].model_id.strip()
        if not model:
            continue
        if model in seen and (slots[name].price_input, slots[name].price_output) != (
            slots[seen[model]].price_input, slots[seen[model]].price_output,
        ):
            problems.append(
                f"{model_env(seen[model])} and {model_env(name)} use the same model "
                "but have different prices"
            )
        seen.setdefault(model, name)

    if settings.app_mode == "live":
        if not settings.endpoint_set:
            problems.append("IBM_ICA_ENDPOINT is not set")
        if not settings.api_key_set:
            problems.append("IBM_ICA_API_KEY is not set")
        if settings.ibm_ica_insecure_tls:
            problems.append("IBM_ICA_INSECURE_TLS is on, so certificates are not being checked")
        for name in SLOT_NAMES:
            cfg = slots[name]
            if not cfg.model_id.strip() and not cfg.fallback_model_id.strip():
                problems.append(f"{model_env(name)} and {fallback_env(name)} are both blank")
        reviewer = slots[routing.reviewer_default]
        if not reviewer.model_id.strip():
            problems.append(
                f"the reviewer slot '{routing.reviewer_default}' has no model; set {model_env(routing.reviewer_default)}"
            )

    rows = []
    for role, slot in routing.roles.items():
        cfg = slots[slot]
        primary = cfg.model_id.strip()
        rows.append(
            {
                "role": role,
                "slot": slot,
                "model": primary or cfg.fallback_model_id.strip(),
                "using_fallback": not primary and bool(cfg.fallback_model_id.strip()),
            }
        )

    reviewer_cfg = slots[routing.reviewer_default]
    return {
        "config_ok": not problems,
        "provider": provider_label,
        "openai_key": "own" if settings.openai_key_is_own else "shared",
        "recordings": recordings_status(settings, recordings),
        "problems": problems,
        "routing": rows,
        "reviewer": {
            "default_slot": routing.reviewer_default,
            "model": reviewer_cfg.model_id.strip() or reviewer_cfg.fallback_model_id.strip(),
            "alternatives": list(routing.reviewer_alternatives),
        },
    }
