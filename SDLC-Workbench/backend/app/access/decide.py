"""May this person take this decision on this phase? One rule, one sentence, used by approving, sending back and by the page that greys the button (S23b).

While nobody is on the Users list nothing is restricted, so a missing ADMIN_NAME can never lock the app. A name that is not on the list, or is switched off, holds no role.
"""
from __future__ import annotations

from typing import Any

from .roles import ROLES


class NotAllowed(Exception):
    """The person holds none of the roles that may take this decision. The text is the plain sentence shown to them."""


def _with_article(role: str) -> str:
    return f"an {role}" if role[0].lower() in "aeiou" else f"a {role}"


def deciding_role(users: Any, actor: str, phase_key: str, phase_name: str, what: str = "approved") -> str | None:
    """The role the person takes the decision as, or None when nothing is restricted. Raises NotAllowed with a sentence naming the role needed and what they hold.
    A person with several allowed roles is recorded under the first, in the fixed order of ROLES."""
    if users.count_active() == 0:
        return None
    allowed = users.approvers().get(phase_key)
    if allowed is None:
        return None
    name = actor.removeprefix("human:")
    me = users.find(name)
    mine = me.roles if me is not None and me.active else ()
    used = next((r for r in ROLES if r in allowed and r in mine), None)
    if used is not None:
        return used
    needs = " or ".join(_with_article(r) for r in allowed)
    if me is None or not me.active:
        raise NotAllowed(f"{phase_name} can be {what} only by {needs}, and {name} is not on the Users list; ask an Administrator to add you")
    held = ", ".join(mine) if mine else "no role"
    raise NotAllowed(f"{phase_name} can be {what} only by {needs}; {me.name} holds {held}")
