from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .errors import RoutingConfigError
from .families import SLOT_NAMES

ROUTING_FILE = Path(__file__).with_name("routing.yaml")

REQUIRED_ROLES = (
    "orchestrator",
    "requirements_analyst",
    "backlog_splitter",
    "ux_designer",
    "solution_architect",
    "diagram_author",
    "database_engineer",
    "backend_developer",
    "frontend_developer",
    "test_engineer",
    "devops_engineer",
    "security_reviewer",
    "handover_author",
    "incident_triage",
)


@dataclass(frozen=True)
class Routing:
    roles: Mapping[str, str]
    reviewer_default: str
    reviewer_alternatives: tuple[str, ...]

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Routing":
        file = Path(path) if path is not None else ROUTING_FILE
        try:
            text = file.read_text(encoding="utf-8")
        except OSError as exc:
            raise RoutingConfigError(f"cannot read routing file {file.name}: {exc.strerror}") from exc
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise RoutingConfigError(f"{file.name} is not valid YAML") from exc
        return cls.from_dict(data, source=file.name)

    @classmethod
    def from_dict(cls, data: Any, source: str = "routing") -> "Routing":
        if not isinstance(data, dict):
            raise RoutingConfigError(f"{source}: expected a mapping with 'roles' and 'reviewer'")

        roles = data.get("roles")
        if not isinstance(roles, dict):
            raise RoutingConfigError(f"{source}: 'roles' must be a mapping of role to slot")
        unknown_roles = sorted(set(roles) - set(REQUIRED_ROLES))
        if unknown_roles:
            raise RoutingConfigError(f"{source}: unknown role(s) {unknown_roles}")
        missing = [r for r in REQUIRED_ROLES if r not in roles]
        if missing:
            raise RoutingConfigError(f"{source}: missing role(s) {missing}")
        for role, slot in roles.items():
            if slot not in SLOT_NAMES:
                raise RoutingConfigError(
                    f"{source}: role '{role}' uses unknown slot {slot!r}; slots are {list(SLOT_NAMES)}"
                )

        reviewer = data.get("reviewer")
        if not isinstance(reviewer, dict):
            raise RoutingConfigError(f"{source}: 'reviewer' must be a mapping with 'default' and 'alternatives'")
        default = reviewer.get("default")
        if default not in SLOT_NAMES:
            raise RoutingConfigError(f"{source}: reviewer default {default!r} is not a known slot")
        alternatives = reviewer.get("alternatives", [])
        if not isinstance(alternatives, list):
            raise RoutingConfigError(f"{source}: reviewer 'alternatives' must be a list of slots")
        for slot in alternatives:
            if slot not in SLOT_NAMES:
                raise RoutingConfigError(f"{source}: reviewer alternative {slot!r} is not a known slot")
        if len(set(alternatives)) != len(alternatives):
            raise RoutingConfigError(f"{source}: reviewer alternatives contain a duplicate")
        if default in alternatives:
            raise RoutingConfigError(f"{source}: reviewer default '{default}' also appears in alternatives")

        return cls(roles=dict(roles), reviewer_default=default, reviewer_alternatives=tuple(alternatives))

    def check_overrides(self, overrides: Mapping[str, str] | None) -> None:
        for role, slot in (overrides or {}).items():
            if role not in self.roles:
                raise RoutingConfigError(f"routing override names unknown role {role!r}")
            if slot not in SLOT_NAMES:
                raise RoutingConfigError(
                    f"routing override for '{role}' uses unknown slot {slot!r}; slots are {list(SLOT_NAMES)}"
                )

    def slot_for(self, role: str, overrides: Mapping[str, str] | None = None) -> str:
        self.check_overrides(overrides)
        if role not in self.roles:
            raise RoutingConfigError(f"unknown role {role!r}; roles are {list(REQUIRED_ROLES)}")
        if overrides and role in overrides:
            return overrides[role]
        return self.roles[role]
