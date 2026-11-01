from __future__ import annotations

from .definitions import Catalogue


def workflow_status(catalogue: Catalogue) -> dict:
    """The lifecycle as the page shows it. Read-only; no project state and no file paths."""
    return {
        "phase_count": len(catalogue.phases),
        "artefact_count": catalogue.artefact_count,
        "required_count": catalogue.required_count,
        "phases": [
            {
                "key": p.key,
                "order": p.order,
                "name": p.name,
                "approver": p.approver,
                "artefacts": len(p.artefacts),
                "required": sum(1 for a in p.artefacts if a.required),
            }
            for p in catalogue.phases
        ],
    }
