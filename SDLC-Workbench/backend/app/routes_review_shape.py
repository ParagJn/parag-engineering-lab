"""How a stored review is shown to the screen. Shared by the artefact detail and the review routes, written once so they cannot differ.

Only what a person reads goes out: the verdict, the summary, each finding, how independent the reviewer was, and what it cost. Call ids,
prompts and raw replies stay in the database.
"""
from __future__ import annotations

from typing import Any


def finding_payload(finding: dict[str, Any]) -> dict[str, Any]:
    out = {
        "severity": str(finding.get("severity", "")), "target": str(finding.get("target", "")),
        "problem": str(finding.get("problem", "")), "fix": str(finding.get("fix", "")),
    }
    if finding.get("source"):
        out["source"] = str(finding["source"])      # only when a finding came from the system's own checks, so every other review reads exactly as before
    return out


def review_payload(record: Any) -> dict[str, Any] | None:
    """A stored review, or None. Only what a person reads: no call ids, no prompts, no raw replies."""
    if not isinstance(record, dict) or "verdict" not in record:
        return None
    independence = record.get("independence") if isinstance(record.get("independence"), dict) else {}
    reviewer = record.get("reviewer") if isinstance(record.get("reviewer"), dict) else {}
    return {
        "version_reviewed": record.get("version_reviewed"), "verdict": record["verdict"], "summary": str(record.get("summary", "")),
        "findings": [finding_payload(f) for f in record.get("findings", []) if isinstance(f, dict)],
        "independence": {
            "label": independence.get("verdict"), "author_family": independence.get("author_family"),
            "reviewer_family": independence.get("reviewer_family"), "fell_back": bool(independence.get("fell_back")),
        },
        "reviewer": {"slot": reviewer.get("slot"), "model": reviewer.get("model"), "family": reviewer.get("family")},
        "cost_usd": record.get("cost_usd"), "attempts": record.get("attempts"),
        "repair_reasons": [
            {"attempt": r.get("attempt"), "problems": [str(p) for p in (r.get("problems") or [])]}
            for r in (record.get("repair_reasons") or []) if isinstance(r, dict)
        ],
    }
