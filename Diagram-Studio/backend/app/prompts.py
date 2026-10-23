"""Prompts for the two model calls: plan (which diagrams?) and draw (spec for one diagram)."""

from __future__ import annotations

import json
from typing import Any

PLAN_SYSTEM = """You are an information architect. You read technical and business documents and decide which diagrams would genuinely help a reader understand them. You answer with JSON only."""

_TYPE_GUIDE = """Diagram types you may choose from:
- architecture: components, services, systems, layers, deployment or integration landscapes; things that are connected or grouped.
- flowchart: a process, workflow, pipeline or decision logic with steps and branches.
- state: something that moves through states or a lifecycle (statuses, approval stages, object lifecycles).
- sequence: actors or systems exchanging messages over time (API calls, handshakes, request/response flows).
- timeline: dated or ordered milestones, phases, roadmaps, history.
- quadrant: items placed on two axes (prioritisation, positioning, effort vs impact, risk matrices)."""


def plan_prompt(text: str, max_diagrams: int) -> str:
    return f"""Read the document below and decide which diagrams to draw.

{_TYPE_GUIDE}

Rules:
- Find every distinct structure worth a diagram. Look for structures stated explicitly (mermaid/plantuml code blocks, ASCII art, numbered step lists, tables of components or phases, headings such as "Architecture", "Flow", "Lifecycle", "Roadmap") and structures that are only described in prose.
- Never invent. Every diagram must be grounded in what the document actually says. If the document supports only one diagram, return one. If it supports none, return an empty list.
- Do not propose two diagrams that show the same thing, and do not diagram trivia. Between 0 and {max_diagrams} diagrams, in the order they appear in the document.
- Pick the type that fits the content best, not the one that is easiest.
- "title": at most six words. "summary": one sentence saying what the diagram shows. "focus": which section or entities of the document to draw from, specific enough that a second reader could draw it without re-deciding.

Return exactly this JSON and nothing else:
{{"document_title": "short title of the document", "diagrams": [{{"type": "architecture", "title": "...", "summary": "...", "focus": "..."}}]}}

DOCUMENT:
<<<
{text}
>>>"""


DIAGRAM_SYSTEM = """You turn one described structure from a document into a precise diagram specification. You answer with a single JSON object and nothing else: no markdown fences, no commentary.

Editorial restraint is the quality bar. The highest-quality move is usually deletion.
- Use only facts from the document. Do not add components, steps or relationships it does not support.
- Aim for 6 to 14 nodes (hard maximum 20). Merge or leave out minor detail rather than cramming everything in.
- Labels are short: one to four words, at most 28 characters. Put technical detail (technology, protocol, port, owner) in "sublabel", at most 40 characters, and leave it empty when the document gives none.
- Mark at most two nodes/items as focal: the thing the diagram is really about. Everything else is not focal.
- Ids are short, lowercase, ASCII, and unique."""


_SCHEMAS: dict[str, str] = {
    "architecture": """{
  "title": "...", "subtitle": "one short line, optional",
  "direction": "LR" or "TB",
  "groups": [{"id": "client", "label": "Client", "parent": null}],
  "nodes": [{"id": "api", "label": "API Gateway", "sublabel": "FastAPI", "kind": "default", "group": "backend"}],
  "edges": [{"from": "web", "to": "api", "label": "HTTPS", "style": "solid"}]
}
- kind is one of: default, focal, muted (peripheral), external (third party / outside the boundary), store (database, queue, file store).
- groups are optional boundaries or tiers that the document actually names; a group may have a "parent" group id for one level of nesting. A node's "group" is a group id or null.
- edges point in the direction of the call or data flow; style is "solid" or "dashed" (async, optional, indirect). Label edges with a verb or protocol only when it adds meaning.
- direction: LR for left-to-right flow, TB for layered top-to-bottom stacks.""",
    "flowchart": """{
  "title": "...", "subtitle": "one short line, optional",
  "direction": "TB" or "LR",
  "nodes": [{"id": "s1", "label": "Receive request", "sublabel": "", "kind": "start"}],
  "edges": [{"from": "s1", "to": "s2", "label": "", "style": "solid"}]
}
- kind is one of: start, end, default (a step), decision (a yes/no or multi-way question), focal, external, store.
- Every decision node has two or more outgoing edges, each labelled with its answer (for example "Yes" / "No").
- A decision node's label is the question itself, short enough to fit inside a diamond (at most 4 words, for example "Record type?"). Leave its "sublabel" empty: put context in the step before or after it, or in an edge label.
- Exactly one start; one or more end nodes. No groups.""",
    "state": """{
  "title": "...", "subtitle": "one short line, optional",
  "direction": "LR" or "TB",
  "nodes": [{"id": "draft", "label": "Draft", "sublabel": "", "kind": "start"}],
  "edges": [{"from": "draft", "to": "review", "label": "submit", "style": "solid"}]
}
- Nodes are states. kind is one of: start (initial state), end (terminal state), default, focal.
- Edges are transitions; label each with the event or trigger. No groups.""",
    "sequence": """{
  "title": "...", "subtitle": "one short line, optional",
  "participants": [{"id": "client", "label": "Client", "sublabel": "browser"}],
  "messages": [{"from": "client", "to": "api", "label": "POST /login", "style": "solid"}]
}
- Participants appear left to right in the order they first act. At most 7.
- Messages are listed top to bottom in time order. style is "solid" for a call and "dashed" for a return or reply. A participant may message itself (from == to). At most 20 messages.""",
    "timeline": """{
  "title": "...", "subtitle": "one short line, optional",
  "events": [{"date": "Q1 2026", "label": "Pilot launch", "detail": "one short sentence, optional", "focal": false}]
}
- Events are in chronological or logical order. Between 3 and 9 events. "date" is whatever the document gives (a date, quarter, phase name, or step number).""",
    "quadrant": """{
  "title": "...", "subtitle": "one short line, optional",
  "x_axis": {"label": "Effort", "low": "Low", "high": "High"},
  "y_axis": {"label": "Impact", "low": "Low", "high": "High"},
  "quadrants": {"top_left": "Quick wins", "top_right": "Major projects", "bottom_left": "Fill-ins", "bottom_right": "Reconsider"},
  "items": [{"label": "Item", "x": 0.3, "y": 0.8, "focal": false}]
}
- x and y are numbers from 0 to 1 (x: 0 is the low end of the x axis, y: 0 is the bottom, 1 is the top). Place items where the document puts them; if it only ranks them, spread them sensibly.
- quadrants names are optional; use an empty string when the document does not name them.""",
}


def diagram_prompt(text: str, item: dict[str, Any]) -> str:
    kind = item["type"]
    return f"""Draw this diagram from the document.

Type: {kind}
Title: {item.get("title", "")}
What it shows: {item.get("summary", "")}
Where to look: {item.get("focus", "")}

Return a JSON object in exactly this shape:
{_SCHEMAS[kind]}

DOCUMENT:
<<<
{text}
>>>"""


ANIM_SYSTEM = """You turn a person's description of an animation into a plan built only from a fixed set of options. You answer with a single JSON object and nothing else: no markdown fences, no commentary.

You cannot invent new effects. If the request asks for something outside the options (colour changes, 3D, sound, text effects, moving individual shapes around), choose the closest options and say what you could not do in "note"."""


def anim_prompt(kind: str, title: str, instruction: str, elements: list[dict[str, Any]]) -> str:
    listing = "\n".join(f'- {e["id"]}: {e.get("label", "")}' for e in elements) or "(none)"
    return f"""Diagram type: {kind}
Diagram title: {title}

The person's request: {instruction}

Options:
- "entrance": "fade" (elements appear one by one, in order), "draw" (like fade, and connections draw themselves in; only for architecture, flowchart and state diagrams) or "none" (starts fully drawn).
- "flow": true or false. Small dots travel along the connections or messages. Only for architecture, flowchart, state and sequence diagrams; use false for the others.
- "emphasis": "pulse" (the named or key elements gently pulse), "walkthrough" (each element is highlighted in turn, on a loop, like a guided tour) or "none".
- "speed": "slow", "normal" or "fast".
- "emphasize": ids from the list below that the request singles out; only meaningful with emphasis "pulse". Use an empty list when it names none.
- "note": one short sentence about anything in the request you could not do, or an empty string.

Elements you may name in "emphasize":
{listing}

Return exactly this JSON:
{{"entrance": "draw", "flow": true, "emphasis": "pulse", "speed": "normal", "emphasize": [], "note": ""}}"""


def plan_item_json(item: dict[str, Any]) -> str:
    return json.dumps(item, ensure_ascii=False)
