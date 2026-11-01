from __future__ import annotations

import re
from typing import Mapping

from ..config import SlotConfig

SLOT_FAMILY = {
    "sonnet": "anthropic",
    "haiku": "anthropic",
    "openai": "openai",
    "gemini": "google",
}
SLOT_NAMES = tuple(SLOT_FAMILY)
UNKNOWN = "unknown"

_PREFIXES = (
    (re.compile(r"claude", re.IGNORECASE), "anthropic"),
    (re.compile(r"(gpt|chatgpt|o\d)", re.IGNORECASE), "openai"),
    (re.compile(r"gemini", re.IGNORECASE), "google"),
)


def env_prefix(slot: str) -> str:
    """Prefix of a slot's .env variables. Sonnet keeps the lab's unprefixed names."""
    return "IBM_ICA" if slot == "sonnet" else f"IBM_ICA_{slot.upper()}"


def model_env(slot: str) -> str:
    return f"{env_prefix(slot)}_MODEL_ID"


def fallback_env(slot: str) -> str:
    return f"{env_prefix(slot)}_FALLBACK_MODEL_ID"


def owner_slot_name(model_id: str, slots: Mapping[str, SlotConfig]) -> str | None:
    """The slot whose own model ID this is, if any."""
    model_id = model_id.strip()
    if not model_id:
        return None
    for name, cfg in slots.items():
        if cfg.model_id.strip() == model_id:
            return name
    return None


def family_of_model(model_id: str, slots: Mapping[str, SlotConfig]) -> str:
    """A model's family: from the slot that owns it, else from its name, else 'unknown'."""
    owner = owner_slot_name(model_id, slots)
    if owner is not None:
        return SLOT_FAMILY[owner]
    for pattern, family in _PREFIXES:
        if pattern.match(model_id.strip()):
            return family
    return UNKNOWN
