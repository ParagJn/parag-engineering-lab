"""Show traceability on the sample project, offline and free: the scripted Setup to Architecture, the chain of one requirement, then the same project with one link cut.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.trace_demo

THE MODEL IS A SCRIPTED FAKE (the Architecture demo's). This shows how the matrix and the gap detector behave, NOT how well a real model links things.
Nothing is called over the network and nothing touches your real database: the project is built in a temporary folder.
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from app.config import Settings
from app.trace.gather import trace_of
from app.trace.traceability import Trace

from .architecture_demo import MODELS, Scripted, run

BANNER = (
    "*** SCRIPTED FAKE MODEL. The links come from replies written in advance inside scripts/architecture_demo.py. ***\n"
    "*** This shows the matrix and the gap detector, NOT how well a real model links things. ***"
)


def describe(trace: Trace, title: str) -> list[str]:
    lines = [f"{title}: {len(trace.chains)} requirements, columns {', '.join(trace.layer_order)}", f"  gaps: {len(trace.gaps) + trace.gaps_more}"]
    lines += [f"    [{g.group}] {g.sentence}" for g in trace.gaps]
    return lines


async def demo(workdir: Path) -> list[str]:
    settings = Settings(_env_file=None, data_dir=str(workdir / "data"), recordings_dir=str(workdir / "rec"), llm_retry_backoff_seconds=0, run_max_cost_usd=0, **MODELS)
    store, pid, result = await run(workdir, settings, Scripted())
    from app.agents.skills import SkillLibrary
    from app.llm.routing import Routing
    from app.workflow.definitions import load_catalogue

    catalogue = load_catalogue(Routing.load().roles.keys())
    skills = SkillLibrary.load(catalogue)
    lines = [BANNER, ""]
    whole = trace_of(store, skills, catalogue, pid)
    lines += describe(whole, "The whole project")
    first = whole.chains[0]
    lines.append(f"  {first.item} ({first.name or 'no name'}) is built on:")
    lines += [f"    {prefix}: {', '.join(first.layers[prefix]) or '-'}" for prefix in whole.layer_order if first.layers[prefix]]
    # cut every link from a component to FR-002 (in the temporary database only): no component now says it serves FR-002
    with store.db.write() as conn:
        conn.execute("DELETE FROM links WHERE project_id = ? AND to_id = 'FR-002' AND from_id LIKE 'COMP-%'", (pid,))
    lines.append("")
    lines += describe(trace_of(store, skills, catalogue, pid), "After cutting one link (every component's link to FR-002)")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    if argv:
        print("This demo takes no options.", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="sdlc_trace_demo_") as tmp:
        print("\n".join(asyncio.run(demo(Path(tmp)))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
