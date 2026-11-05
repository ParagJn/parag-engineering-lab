"""The roles, the default approver of each phase, and the rule for turning a typed name into a user (S23a). Pure data and pure functions: no database, no model.

A role is a short fixed name. A person can hold several. Which roles may approve a phase is a setting that starts from DEFAULT_APPROVERS (the user's words: Requirements and
Design are approved by an architect) and can be changed on the Users screen (23c).
"""
from __future__ import annotations

import re

ROLES = ("Project Manager", "Architect", "Business Engineer", "Technical Lead", "Deployment Engineer", "BAU Lead", "Administrator")
ADMIN = "Administrator"
MAX_NAME = 60
_NAME = re.compile(r"[^\x00-\x1f\x7f]+")
RESERVED = ("system",)

# The phases in order, and who approves each by default. Setup, Requirements and Design: Architect (the user's example). The others follow the "approver" label of the phase.
DEFAULT_APPROVERS: dict[str, tuple[str, ...]] = {
    "setup": ("Architect",),
    "requirements": ("Architect",),
    "design": ("Architect",),
    "architecture": ("Technical Lead",),
    "build": ("Technical Lead",),
    "deploy": ("Deployment Engineer",),
    "handover": ("BAU Lead",),
}


class RoleError(ValueError):
    """A plain sentence a person can read: an unknown role, a bad name, the last administrator."""


def clean_name(raw: str) -> str:
    """A person's name as the app stores it: spaces tidied, no control characters, not reserved, not too long. The same rule X-Actor already applies."""
    if any(ord(c) < 32 or ord(c) == 127 for c in (raw or "")):                # checked on the raw text, as X-Actor does: a newline is refused, not turned into a space
        raise RoleError("that name contains characters that are not allowed, or is reserved")
    name = " ".join((raw or "").split())
    if not name:
        raise RoleError("a name is needed")
    if len(name) > MAX_NAME:
        raise RoleError(f"a name is at most {MAX_NAME} characters")
    if not _NAME.fullmatch(name) or name.lower() in RESERVED or name.lower().startswith(("human:", "agent:")):
        raise RoleError("that name contains characters that are not allowed, or is reserved")
    return name


def clean_roles(roles) -> tuple[str, ...]:
    """The roles in their fixed order, each once. An unknown role is refused by name, listing the roles that exist."""
    asked = list(roles or [])
    unknown = [r for r in asked if r not in ROLES]
    if unknown:
        raise RoleError(f"unknown role {unknown[0]!r}; the roles are {', '.join(ROLES)}")
    return tuple(r for r in ROLES if r in asked)


def same_person(a: str, b: str) -> bool:
    """Names are matched without regard to case or extra spaces, so 'ann' and 'Ann ' are one person."""
    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()
