from __future__ import annotations

from .scan import ALWAYS_ON, RULES, Scanner


def guardrails_status(scanner: Scanner) -> dict:
    """Rule counts and the names of anything switched off, so a disabled rule is never silent. No patterns, no values."""
    return {
        "rules": len(RULES),
        "secret_rules": sum(1 for r in RULES if r.klass == "secret"),
        "personal_rules": sum(1 for r in RULES if r.klass == "personal"),
        "disabled": sorted(scanner.disabled),
        "cannot_be_disabled": sorted(ALWAYS_ON),
    }
