"""Traceability over HTTP (S15). Read-only: it changes nothing, so it needs no name, and an archived project can still be read.

The answer holds item IDs, short names and the sentences the server computed. It never holds an artefact's body, a prompt, a key or a path.
"""
from __future__ import annotations

import csv
import io
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from .models import InvalidInput, NotFoundError
from .trace.gather import trace_of
from .trace.traceability import Gap, Trace, ancestors, descendants, prefix_of, sort_key

router = APIRouter(prefix="/api/projects/{project_id}")

_ITEM = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3,}$")
_FORMULA = ("=", "+", "-", "@", "\t", "\r")
NO_ITEMS = "-"                                                       # what an empty cell shows in the CSV


def safe_cell(value: str) -> str:
    """A spreadsheet runs a cell that starts with = + - or @ as a formula. A leading apostrophe makes it plain text, and costs nothing to read."""
    text = "" if value is None else str(value)
    if text == NO_ITEMS:
        return text                                                  # our own marker for an empty cell; on its own it cannot be read as a formula
    return "'" + text if text.startswith(_FORMULA) else text


def gap_payload(gap: Gap) -> dict[str, Any]:
    return {
        "kind": gap.kind, "group": gap.group, "item": gap.item, "artefact_id": gap.artefact_id, "version": gap.version, "other": gap.other,
        "reason": gap.reason, "by": gap.by, "sentence": gap.sentence,
    }


def trace_payload(trace: Trace) -> dict[str, Any]:
    gaps = [gap_payload(g) for g in trace.gaps]
    return {
        "layers": list(trace.layer_order),
        "chains": [
            {"item": c.item, "name": c.name, "cells": [{"layer": p, "state": c.states[p], "items": list(c.layers[p])} for p in trace.layer_order]}
            for c in trace.chains
        ],
        "gaps": gaps, "gaps_more": trace.gaps_more,
        "needs_attention": sum(1 for g in gaps if g["group"] == "needs_attention"), "explained": sum(1 for g in gaps if g["group"] == "explained"),
        "counts": dict(trace.counts),
        "names": {i.id: i.name for i in trace.items.values() if i.name and not i.withdrawn},
        "artefacts": {i.id: i.artefact_id for i in trace.items.values()},
    }


def _trace(request: Request, project_id: str) -> Trace:
    state = request.app.state
    try:
        state.store.projects.get(project_id)
        return trace_of(state.store, state.skills, state.engine.catalogue, project_id)
    except (NotFoundError, InvalidInput) as exc:
        raise HTTPException(status_code=404 if isinstance(exc, NotFoundError) else 422, detail=str(exc)) from exc


@router.get("/traceability")
def traceability(project_id: str, request: Request) -> dict:
    return trace_payload(_trace(request, project_id))


@router.get("/traceability/item/{item_id}")
def trace_item(project_id: str, item_id: str, request: Request) -> dict:
    """One item with what it comes from and what was built on it, nearest first, each with its short name."""
    if not _ITEM.fullmatch(item_id):
        raise HTTPException(status_code=422, detail="item id has unexpected characters")
    state = request.app.state
    trace = _trace(request, project_id)
    if item_id not in trace.items:
        raise HTTPException(status_code=404, detail=f"{item_id} is not an item in this project")
    links = [(l.from_id, l.to_id) for l in state.store.links.list(project_id)]

    def row(i: str) -> dict[str, Any]:
        found = trace.items.get(i)
        return {"id": i, "name": found.name if found else "", "artefact_id": found.artefact_id if found else None, "withdrawn": bool(found and found.withdrawn), "known": found is not None}
    return {"item": row(item_id), "comes_from": [row(i) for i in ancestors(item_id, links)], "built_on_it": [row(i) for i in descendants(item_id, links)],
            "gaps": [gap_payload(g) for g in trace.gaps if g.item == item_id or g.other == item_id]}


@router.get("/traceability/export.csv")
def export_csv(project_id: str, request: Request) -> Response:
    trace = _trace(request, project_id)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(["Requirement", "Name", *trace.layer_order])
    for chain in trace.chains:
        cells = []
        for prefix in trace.layer_order:
            state = chain.states[prefix]
            cells.append(" ".join(chain.layers[prefix]) if state == "built" else ("not started" if state == "not_started" else NO_ITEMS))
        writer.writerow([safe_cell(chain.item), safe_cell(chain.name), *[safe_cell(c) for c in cells]])
    return Response(out.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="traceability.csv"'})
