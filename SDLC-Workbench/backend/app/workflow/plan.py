"""From the wizard's choices to a plan: which artefacts run, and in what parallel waves.

Pure data. No database, no models, so every rule here is testable on its own.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .definitions import ArtefactDef, Catalogue, PhaseDef


class PlanError(ValueError):
    """The selection asks for something the catalogue does not allow."""


@dataclass(frozen=True)
class PhasePlan:
    phase: PhaseDef
    artefacts: tuple[ArtefactDef, ...]  # enabled ones, in catalogue order
    waves: tuple[tuple[ArtefactDef, ...], ...]  # parallel groups; each waits only for earlier waves
    pulled_in: tuple[str, ...]  # artefact keys added because something enabled needs them

    @property
    def key(self) -> str:
        return self.phase.key

    @property
    def required(self) -> tuple[ArtefactDef, ...]:
        return tuple(a for a in self.artefacts if a.required)

    def has(self, artefact_key: str) -> bool:
        return any(a.key == artefact_key for a in self.artefacts)


@dataclass(frozen=True)
class Plan:
    phases: tuple[PhasePlan, ...]  # lifecycle order

    def phase(self, key: str) -> PhasePlan:
        for item in self.phases:
            if item.key == key:
                return item
        raise KeyError(key)

    @property
    def notes(self) -> tuple[str, ...]:
        """Plain sentences about anything the plan changed on the user's behalf."""
        out = []
        for phase in self.phases:
            for key in phase.pulled_in:
                needed_by = sorted(a.name for a in phase.artefacts if key in a.after)
                out.append(
                    f"{phase.phase.name}: '{phase.phase.artefact(key).name}' was added because "
                    f"{', '.join(repr(n) for n in needed_by)} needs it"
                )
        return tuple(out)


def compute_waves(artefacts: tuple[ArtefactDef, ...]) -> tuple[tuple[ArtefactDef, ...], ...]:
    """Layer artefacts by their `after` rules. Everything inside one wave can run at the same time."""
    keys = {a.key for a in artefacts}
    placed: dict[str, int] = {}
    remaining = list(artefacts)
    waves: list[list[ArtefactDef]] = []
    while remaining:
        ready = [a for a in remaining if all(d in placed for d in a.after if d in keys)]
        if not ready:  # cannot happen for a validated catalogue; guards against a hand-built one
            raise PlanError("the 'after' rules cannot be satisfied (a loop)")
        for item in ready:
            placed[item.key] = len(waves)
        waves.append(ready)  # `remaining` is in catalogue order, so each wave is too
        remaining = [a for a in remaining if a.key not in placed]
    return tuple(tuple(w) for w in waves)


def _enabled_keys(phase: PhaseDef, choice: Any) -> tuple[set[str], set[str]]:
    """(keys to enable, keys pulled in as dependencies) for one phase.

    `choice` is None (everything) or the list of artefact keys the wizard left switched ON. Required
    artefacts must be in that list: leaving one out is an error, not a silent re-add, so what the
    user asked for and what they get can never differ without being told.
    """
    if choice is None:
        enabled = {a.key for a in phase.artefacts}
        return enabled, set()

    if not isinstance(choice, (list, tuple, set)) or not all(isinstance(k, str) for k in choice):
        raise PlanError(f"selection for '{phase.key}' must be a list of artefact keys or null")
    enabled = set(choice)
    known = {a.key for a in phase.artefacts}
    unknown = sorted(enabled - known)
    if unknown:
        raise PlanError(f"phase '{phase.key}' has no artefact(s) {unknown}")
    left_out = [a.name for a in phase.artefacts if a.required and a.key not in enabled]
    if left_out:
        raise PlanError(
            f"{phase.name}: {', '.join(repr(n) for n in left_out)} "
            f"{'is' if len(left_out) == 1 else 'are'} required and cannot be switched off"
        )

    pulled: set[str] = set()
    grew = True
    while grew:
        grew = False
        for item in phase.artefacts:
            if item.key in enabled:
                for dependency in item.after:
                    if dependency not in enabled:
                        enabled.add(dependency)
                        pulled.add(dependency)
                        grew = True
    return enabled, pulled


def build_plan(catalogue: Catalogue, selection: Mapping[str, Any] | None) -> Plan:
    """Turn the wizard's selection into a plan.

    `selection` maps a phase key to the list of artefact keys switched ON (or None for all of them).
    A phase missing from the mapping gets everything. Required artefacts must be on, a dependency of
    something that is on is added and reported, and unknown keys are errors.
    """
    selection = dict(selection or {})
    unknown_phases = sorted(set(selection) - set(catalogue.phase_keys))
    if unknown_phases:
        raise PlanError(f"selection names unknown phase(s) {unknown_phases}; phases are {list(catalogue.phase_keys)}")

    phases: list[PhasePlan] = []
    for phase in catalogue.phases:
        enabled, pulled = _enabled_keys(phase, selection.get(phase.key))
        artefacts = tuple(a for a in phase.artefacts if a.key in enabled)
        phases.append(PhasePlan(phase, artefacts, compute_waves(artefacts), tuple(sorted(pulled))))
    return Plan(tuple(phases))
