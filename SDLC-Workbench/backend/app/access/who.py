"""How a phase's approvers are written in words (S23). The label in the phase definition ("business engineer") is only a fallback now: what is shown follows the roles
that may approve the phase, which an Administrator can change. One function, so the page, the 'awaiting review' sentence and the audit all say the same thing."""
from __future__ import annotations

from typing import Mapping, Sequence

def role_words(role: str) -> str:
    """A role as it reads inside a sentence, in lower case like the old labels were: 'Architect' -> 'architect', 'Technical Lead' -> 'technical lead'. 'BAU' is an acronym and keeps
    its capitals: 'BAU Lead' -> 'BAU lead'."""
    first, _, rest = role.partition(" ")
    return " ".join(w if w.isupper() else w.lower() for w in [first, *rest.split()] if w)


def approvers_in_words(roles: Sequence[str]) -> str:
    """'architect', 'architect or technical lead', 'architect, technical lead or BAU Lead'. Empty gives an empty string (the caller falls back to the definition's label)."""
    words = [role_words(r) for r in roles]
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " or " + words[-1]


def approver_label(phase_key: str, fallback: str, approvers: Mapping[str, Sequence[str]] | None) -> str:
    """What to show as the phase's approver: the configured roles in words, or the definition's own label when nothing is configured for it."""
    roles = (approvers or {}).get(phase_key) or ()
    return approvers_in_words(roles) or fallback
