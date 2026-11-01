from __future__ import annotations

from ..workflow.definitions import Catalogue
from .skills import SkillLibrary


def skills_status(catalogue: Catalogue, library: SkillLibrary) -> dict:
    """Counts and names only. No file paths and no skill text."""
    return {
        "with_skill": len(library),
        "artefacts": catalogue.artefact_count,
        "keys": sorted(library.keys),
    }
