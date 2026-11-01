from __future__ import annotations

from typing import Mapping

from ..config import SlotConfig
from .families import owner_slot_name
from .types import Usage


def cost_usd(slot: SlotConfig | None, usage: Usage | None) -> float | None:
    """Estimated cost of one call, or None when it can't be known (never zero by default)."""
    if slot is None or usage is None or not slot.priced:
        return None
    return usage.tokens_in * slot.price_input / 1e6 + usage.tokens_out * slot.price_output / 1e6


def pricing_slot(model_id: str, slots: Mapping[str, SlotConfig]) -> SlotConfig | None:
    """The slot whose prices apply to the model that served a call."""
    owner = owner_slot_name(model_id, slots)
    return slots[owner] if owner is not None else None
