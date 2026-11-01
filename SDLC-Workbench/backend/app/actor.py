"""Who is acting, for the HTTP layer.

There is no sign-in: the screen asks for a name and sends it in `X-Actor`. It is a label for the audit trail, not a credential, and
the server says so in its error. The rule is the same one the repository already applies (`human:<name>`), with a bound on the
length and a refusal of control characters, so nothing odd can reach the audit log through a header.
"""
from __future__ import annotations

from fastapi import HTTPException, Request

MAX_NAME_CHARS = 60
HEADER = "x-actor"


def actor_from(request: Request) -> str:
    raw = request.headers.get(HEADER)
    if raw is None:
        raise HTTPException(status_code=400, detail="this action needs a name for the audit trail: send it in the X-Actor header (a label, not a sign-in)")
    name = " ".join(raw.split())
    if not name:
        raise HTTPException(status_code=400, detail="the name in X-Actor is blank; use a name to put in the audit trail")
    if len(name) > MAX_NAME_CHARS:
        raise HTTPException(status_code=400, detail=f"the name in X-Actor is longer than {MAX_NAME_CHARS} characters")
    if any(ord(c) < 32 or ord(c) == 127 for c in raw) or name.lower() in ("system",) or name.lower().startswith(("human:", "agent:")):
        raise HTTPException(status_code=400, detail="the name in X-Actor contains characters that are not allowed, or is reserved")
    return f"human:{name}"
