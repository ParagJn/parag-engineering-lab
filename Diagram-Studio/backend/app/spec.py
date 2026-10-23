"""Clean up diagram specs from the model.

The model is asked for strict JSON, but it still drifts: dangling edges, duplicate ids, ten "focal" nodes,
essay-length labels. Everything is normalised here so the renderer can trust what it gets.
"""

from __future__ import annotations

import re
from typing import Any

GRAPH_TYPES = ("architecture", "flowchart", "state")
DIAGRAM_TYPES = (*GRAPH_TYPES, "sequence", "timeline", "quadrant")

_TYPE_ALIASES = {
    "architecture": "architecture",
    "system": "architecture",
    "network": "architecture",
    "component": "architecture",
    "infrastructure": "architecture",
    "layered": "architecture",
    "flowchart": "flowchart",
    "flow": "flowchart",
    "process": "flowchart",
    "workflow": "flowchart",
    "decision": "flowchart",
    "state": "state",
    "statemachine": "state",
    "lifecycle": "state",
    "sequence": "sequence",
    "interaction": "sequence",
    "timeline": "timeline",
    "roadmap": "timeline",
    "chronology": "timeline",
    "quadrant": "quadrant",
    "matrix": "quadrant",
    "2x2": "quadrant",
}

NODE_KINDS = {"default", "focal", "muted", "external", "store", "start", "end", "decision"}

MAX_NODES = 24
MAX_EDGES = 40
MAX_GROUPS = 8
MAX_PARTICIPANTS = 8
MAX_MESSAGES = 26
MAX_EVENTS = 10
MAX_ITEMS = 14
MAX_FOCAL = 2


def normalize_type(value: Any) -> str:
    key = re.sub(r"[^a-z0-9]", "", str(value or "").lower().replace("diagram", ""))
    return _TYPE_ALIASES.get(key, "architecture")


def _text(value: Any, limit: int) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _unique_ids(items: list[dict], prefix: str) -> None:
    """Give every item a usable, unique, string id (in place)."""
    seen: set[str] = set()
    for index, item in enumerate(items):
        base = re.sub(r"[^A-Za-z0-9_.-]", "_", str(item.get("id") or "").strip()) or f"{prefix}{index + 1}"
        candidate, n = base, 2
        while candidate in seen:
            candidate = f"{base}_{n}"
            n += 1
        seen.add(candidate)
        item["_orig"] = str(item.get("id") or "").strip()
        item["id"] = candidate


def _id_lookup(items: list[dict]) -> dict[str, str]:
    """Map every id the model may have used (original or cleaned) to the cleaned id."""
    lookup: dict[str, str] = {}
    for item in items:
        lookup.setdefault(item["id"], item["id"])
        if item.get("_orig"):
            lookup.setdefault(item["_orig"], item["id"])
    return lookup


def _list(value: Any) -> list[dict]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _header(raw: dict, kind: str, fallback_title: str) -> dict[str, Any]:
    return {
        "type": kind,
        "title": _text(raw.get("title"), 80) or fallback_title,
        "subtitle": _text(raw.get("subtitle"), 140),
    }


def sanitize(raw: dict, kind: str, fallback_title: str) -> dict[str, Any]:
    if kind in GRAPH_TYPES:
        return _graph(raw, kind, fallback_title)
    if kind == "sequence":
        return _sequence(raw, fallback_title)
    if kind == "timeline":
        return _timeline(raw, fallback_title)
    if kind == "quadrant":
        return _quadrant(raw, fallback_title)
    raise ValueError(f"Unknown diagram type '{kind}'.")


def _graph(raw: dict, kind: str, fallback_title: str) -> dict[str, Any]:
    groups = _list(raw.get("groups"))[:MAX_GROUPS]
    _unique_ids(groups, "g")
    group_lookup = _id_lookup(groups)

    nodes = _list(raw.get("nodes"))[:MAX_NODES]
    _unique_ids(nodes, "n")
    node_lookup = _id_lookup(nodes)
    if len(nodes) < 2:
        raise ValueError("The diagram needs at least two nodes.")

    clean_groups = []
    for group in groups:
        parent = group_lookup.get(str(group.get("parent") or "").strip())
        clean_groups.append({"id": group["id"], "label": _text(group.get("label"), 40) or group["id"], "parent": parent if parent != group["id"] else None})
    parents = {g["id"]: g["parent"] for g in clean_groups}
    for group in clean_groups:  # break parent cycles
        seen, cursor = {group["id"]}, group["parent"]
        while cursor:
            if cursor in seen:
                group["parent"] = None
                parents[group["id"]] = None
                break
            seen.add(cursor)
            cursor = parents.get(cursor)

    focal_seen = 0
    clean_nodes = []
    for node in nodes:
        node_kind = str(node.get("kind") or "default").strip().lower()
        if node_kind not in NODE_KINDS:
            node_kind = "default"
        if node_kind == "focal":
            focal_seen += 1
            if focal_seen > MAX_FOCAL:
                node_kind = "default"
        clean_nodes.append(
            {
                "id": node["id"],
                "label": _text(node.get("label"), 40) or node["id"],
                # A diamond has no room for a second line of text
                "sublabel": "" if node_kind == "decision" else _text(node.get("sublabel"), 56),
                "kind": node_kind,
                "group": group_lookup.get(str(node.get("group") or "").strip()),
            }
        )

    clean_edges, seen_edges = [], set()
    for edge in _list(raw.get("edges")):
        source = node_lookup.get(str(edge.get("from") or "").strip())
        target = node_lookup.get(str(edge.get("to") or "").strip())
        if not source or not target or source == target:
            continue
        label = _text(edge.get("label"), 32)
        key = (source, target, label)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        style = "dashed" if str(edge.get("style") or "").lower() == "dashed" else "solid"
        clean_edges.append({"from": source, "to": target, "label": label, "style": style, "both": bool(edge.get("bidirectional"))})
        if len(clean_edges) >= MAX_EDGES:
            break

    direction = str(raw.get("direction") or "").upper()
    if direction not in {"TB", "LR"}:
        direction = "TB" if kind in {"flowchart", "state"} else "LR"

    return {
        **_header(raw, kind, fallback_title),
        "direction": direction,
        "groups": clean_groups,
        "nodes": clean_nodes,
        "edges": clean_edges,
    }


def _sequence(raw: dict, fallback_title: str) -> dict[str, Any]:
    participants = _list(raw.get("participants"))[:MAX_PARTICIPANTS]
    _unique_ids(participants, "p")
    lookup = _id_lookup(participants)
    if len(participants) < 2:
        raise ValueError("The sequence diagram needs at least two participants.")

    messages = []
    for message in _list(raw.get("messages")):
        source = lookup.get(str(message.get("from") or "").strip())
        target = lookup.get(str(message.get("to") or "").strip())
        if not source or not target:
            continue
        messages.append(
            {
                "from": source,
                "to": target,
                "label": _text(message.get("label"), 44),
                "style": "dashed" if str(message.get("style") or "").lower() == "dashed" else "solid",
            }
        )
        if len(messages) >= MAX_MESSAGES:
            break
    if not messages:
        raise ValueError("The sequence diagram has no usable messages.")

    return {
        **_header(raw, "sequence", fallback_title),
        "participants": [
            {"id": p["id"], "label": _text(p.get("label"), 28) or p["id"], "sublabel": _text(p.get("sublabel"), 40)} for p in participants
        ],
        "messages": messages,
    }


def _timeline(raw: dict, fallback_title: str) -> dict[str, Any]:
    events = []
    focal_seen = 0
    for event in _list(raw.get("events"))[:MAX_EVENTS]:
        label = _text(event.get("label"), 40)
        if not label:
            continue
        focal = bool(event.get("focal")) and focal_seen < MAX_FOCAL
        focal_seen += 1 if focal else 0
        events.append({"label": label, "date": _text(event.get("date"), 24), "detail": _text(event.get("detail"), 90), "focal": focal})
    if len(events) < 2:
        raise ValueError("The timeline needs at least two events.")
    return {**_header(raw, "timeline", fallback_title), "events": events}


def _unit(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    return min(max(number, 0.04), 0.96)


def _quadrant(raw: dict, fallback_title: str) -> dict[str, Any]:
    items = []
    focal_seen = 0
    for item in _list(raw.get("items"))[:MAX_ITEMS]:
        label = _text(item.get("label"), 32)
        if not label:
            continue
        focal = bool(item.get("focal")) and focal_seen < MAX_FOCAL
        focal_seen += 1 if focal else 0
        items.append({"label": label, "x": _unit(item.get("x")), "y": _unit(item.get("y")), "focal": focal})
    if len(items) < 2:
        raise ValueError("The quadrant needs at least two items.")

    def axis(key: str) -> dict[str, str]:
        value = raw.get(key) if isinstance(raw.get(key), dict) else {}
        return {"label": _text(value.get("label"), 32), "low": _text(value.get("low"), 24) or "Low", "high": _text(value.get("high"), 24) or "High"}

    quadrants = raw.get("quadrants") if isinstance(raw.get("quadrants"), dict) else {}
    return {
        **_header(raw, "quadrant", fallback_title),
        "x_axis": axis("x_axis"),
        "y_axis": axis("y_axis"),
        "quadrants": {key: _text(quadrants.get(key), 28) for key in ("top_left", "top_right", "bottom_left", "bottom_right")},
        "items": items,
    }
