"""Animation plans.

The model never writes CSS or SVG. It only picks from a small, fixed vocabulary (below), and the browser turns the
chosen options into CSS keyframes inside the exported SVG. That keeps every animation valid, self-contained and safe.
"""

from __future__ import annotations

from typing import Any

ENTRANCES = ("fade", "draw", "none")
EMPHASES = ("pulse", "walkthrough", "none")
SPEEDS = ("slow", "normal", "fast")

GRAPH_TYPES = ("architecture", "flowchart", "state")
FLOW_TYPES = (*GRAPH_TYPES, "sequence")
MAX_EMPHASIZE = 6


def default_plan(kind: str) -> dict[str, Any]:
    """The best all-round animation for each diagram type, used when the user does not ask for anything specific."""
    if kind == "timeline":
        emphasis = "walkthrough"
    elif kind == "sequence":
        emphasis = "none"
    else:
        emphasis = "pulse"
    return {
        "entrance": "draw" if kind in GRAPH_TYPES else "fade",
        "flow": kind in FLOW_TYPES,
        "emphasis": emphasis,
        "speed": "normal",
        "emphasize": [],
    }


def describe(plan: dict[str, Any], kind: str) -> str:
    """A plain-language summary, built from the plan itself so it can never disagree with what is drawn."""
    parts: list[str] = []
    if plan["entrance"] == "draw":
        parts.append("elements appear in order and the connections draw themselves in")
    elif plan["entrance"] == "fade":
        parts.append("elements appear one by one, in order")
    else:
        parts.append("starts fully drawn")
    if plan["flow"]:
        parts.append("dots travel along each message" if kind == "sequence" else "dots travel along the connections")
    if plan["emphasis"] == "pulse":
        parts.append("the highlighted parts pulse" if plan["emphasize"] else "the key parts pulse")
    elif plan["emphasis"] == "walkthrough":
        parts.append("each step is highlighted in turn, on a loop")
    if plan["speed"] != "normal":
        parts.append(f"{plan['speed']} pace")
    return ". ".join(p[0].upper() + p[1:] for p in parts) + "."


def finalize(plan: dict[str, Any], has_focal: bool) -> str:
    """Make the plan honest about what will move. Returns a note when something had to change.

    A pulse with nothing named and no focal element in the diagram would animate nothing, so it is dropped.
    """
    if plan["emphasis"] == "pulse" and not plan["emphasize"] and not has_focal:
        plan["emphasis"] = "none"
        return "Nothing in this diagram is highlighted, so there was nothing to pulse. Name a part to pulse it."
    return ""


def is_static(plan: dict[str, Any]) -> bool:
    return plan["entrance"] == "none" and not plan["flow"] and plan["emphasis"] == "none"


def sanitize_plan(raw: dict[str, Any], kind: str, valid_ids: set[str]) -> dict[str, Any]:
    base = default_plan(kind)

    def pick(value: Any, options: tuple[str, ...], fallback: str) -> str:
        text = str(value or "").strip().lower()
        return text if text in options else fallback

    entrance = pick(raw.get("entrance"), ENTRANCES, base["entrance"])
    if entrance == "draw" and kind not in GRAPH_TYPES:
        entrance = "fade"

    flow = raw.get("flow")
    flow = base["flow"] if not isinstance(flow, bool) else flow
    if kind not in FLOW_TYPES:
        flow = False

    emphasis = pick(raw.get("emphasis"), EMPHASES, base["emphasis"])
    listed = raw.get("emphasize")
    emphasize = [str(v) for v in listed if str(v) in valid_ids][:MAX_EMPHASIZE] if isinstance(listed, list) else []
    if emphasis != "pulse":
        emphasize = []

    return {
        "entrance": entrance,
        "flow": flow,
        "emphasis": emphasis,
        "speed": pick(raw.get("speed"), SPEEDS, "normal"),
        "emphasize": emphasize,
    }
