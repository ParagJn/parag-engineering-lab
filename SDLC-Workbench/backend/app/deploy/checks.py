"""The checks a person works through by hand, one list per phase (S21c, S22a). Fixed in code and shown as text; nothing here calls a model.

Each check is one question a person can answer by looking, with a stable ID so an answer stays attached to the same question. A list is grouped the way the phase goes and
ends with one overall decision. The answer is kept as `go`, `no_go` or `not_applicable` whatever the list calls them on the page. Editing a list is parked; a person writes
what else they need in the note beside a check.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

ANSWERS = ("go", "no_go", "not_applicable")
ANSWER_WORDS = {"go": "Go", "no_go": "No-go", "not_applicable": "Not applicable"}          # the Deploy wording; another list may word them differently
MAX_NOTE_CHARS = 1000
CHECK_ID = re.compile(r"[A-Z]{3}-\d{3}")


@dataclass(frozen=True)
class Check:
    id: str
    group: str
    question: str
    from_where: str = ""                     # the document or step the question comes from, in words


@dataclass(frozen=True)
class ChecklistDef:
    """One phase's list: its checks, groups, wording and the check that is the overall decision. Checked when it is made, so a broken list cannot be imported."""
    phase: str
    title: str                               # the heading of the panel and the report ("Deployment checklist")
    report_title: str                        # the first line of the one-page report
    groups: tuple[str, ...]
    group_title: dict
    decision_id: str
    checks: tuple[Check, ...]
    open_items_key: str                      # the name this list's open items have in the approval record
    answer_words: dict

    def __post_init__(self) -> None:
        ids = [c.id for c in self.checks]
        if len(set(ids)) != len(ids):
            raise ValueError(f"{self.phase}: a check ID is used twice")
        if not all(CHECK_ID.fullmatch(i) for i in ids):
            raise ValueError(f"{self.phase}: every check ID looks like ABC-001")
        if not all(c.group in self.groups for c in self.checks):
            raise ValueError(f"{self.phase}: a check is in a group the list does not have")
        if set(self.group_title) != set(self.groups) or set(self.answer_words) != set(ANSWERS):
            raise ValueError(f"{self.phase}: every group needs a title and every answer a word")
        decision = {c.id: c for c in self.checks}.get(self.decision_id)
        if decision is None or decision.group != "decision" or self.checks[-1] is not decision or [c for c in self.checks if c.group == "decision"] != [decision]:
            raise ValueError(f"{self.phase}: the decision must be the one check of the 'decision' group, and the last check")

    @property
    def by_id(self) -> dict:
        return {c.id: c for c in self.checks}

    def of_group(self, group: str) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.group == group)


_DEPLOY_CHECKS: tuple[Check, ...] = (
    Check("CHK-001", "ready", "The deployment plan has been read and the people who will do the release agree with it.", "the deployment plan"),
    Check("CHK-002", "ready", "The release notes have been read and say what the people using the product need to know.", "the release notes"),
    Check("CHK-003", "ready", "The people who need to know about the release have been told when it happens.", "the release notes"),
    Check("CHK-004", "ready", "A way back has been agreed, and the person who will do it is named.", "the rollback section of the plan"),
    Check("CHK-005", "before", "The build has been compared with the design, and what differs has been looked at.", "Build Verify"),
    Check("CHK-006", "before", "The settings and secrets the product needs are in place, and none of them is in the code.", "the configuration section of the plan"),
    Check("CHK-007", "before", "Anything that changes stored data can be undone: there is a backup or another way back.", "the data section of the plan"),
    Check("CHK-008", "before", "The place being released to is the one the plan names.", "the environments section of the plan"),
    Check("CHK-009", "after", "The product starts and stays running.", "the steps of the plan"),
    Check("CHK-010", "after", "The main thing the product is for works once, from start to finish, when tried by hand.", "the release notes"),
    Check("CHK-011", "after", "Each page or feature named in the release notes opens or responds.", "the release notes"),
    Check("CHK-012", "after", "Nothing in the logs or on the screen looks wrong or alarming.", ""),
    Check("CHK-013", "after", "The people the product is for can reach it.", ""),
    Check("CHK-014", "after", "Data the product keeps is being saved, and can be read back.", "the data section of the plan"),
    Check("CHK-015", "after", "Anything that was said would not work in the release notes (known limits) behaves as described.", "the known limits in the release notes"),
    Check("CHK-016", "decision", "Overall: go. The release is good to keep, and the people who need to know have been told.", ""),
)

DEPLOY = ChecklistDef(
    phase="deploy", title="Deployment checklist", report_title="Deployment verification",
    groups=("ready", "before", "after", "decision"),
    group_title={"ready": "Ready to go", "before": "Before the release", "after": "After the release", "decision": "The decision"},
    decision_id="CHK-016", checks=_DEPLOY_CHECKS, open_items_key="deployment_checks", answer_words=dict(ANSWER_WORDS),
)

# BAU handover's sign-off (S22c): statements support accepts or does not accept, one by one. The answer is kept as go / no_go / not_applicable like every list;
# on the page and in the report it reads Accept / Not accepted / Not applicable. Who signed is the person who answered; their role is written in the note of the decision.
_HANDOVER_CHECKS: tuple[Check, ...] = (
    Check("SGN-001", "given", "The support team has read the runbook and finds it usable for looking after the product.", "the runbook"),
    Check("SGN-002", "given", "The support team has read the hypercare plan and agrees with it: who is on hand, for how long, and when it ends.", "the hypercare plan"),
    Check("SGN-003", "given", "The support team knows who to ask, and how to reach the people who built the product.", "the contacts in the runbook"),
    Check("SGN-004", "can", "The support team can start, stop and check the product by following the runbook.", "the runbook"),
    Check("SGN-005", "can", "The support team knows what to do first when something goes wrong, and when to ask for help.", "the runbook and the hypercare plan"),
    Check("SGN-006", "can", "The support team can go back to the earlier release by following the rollback in the deployment plan.", "the deployment plan"),
    Check("SGN-007", "can", "The support team has the access it needs to the product, its settings and its logs.", ""),
    Check("SGN-008", "decision", "Overall: accept. Support accepts the product and takes over its day-to-day care. Write your role in the note.", ""),
)

HANDOVER = ChecklistDef(
    phase="handover", title="Handover sign-off", report_title="Handover sign-off",
    groups=("given", "can", "decision"),
    group_title={"given": "What support has been given", "can": "What support can do", "decision": "The decision"},
    decision_id="SGN-008", checks=_HANDOVER_CHECKS, open_items_key="handover_signoff",
    answer_words={"go": "Accept", "no_go": "Not accepted", "not_applicable": "Not applicable"},
)

# Every phase that has a checklist, by phase key. A phase not in this table has none.
LISTS: dict = {"deploy": DEPLOY, "handover": HANDOVER}


def definition_of(phase: str) -> ChecklistDef:
    """The list for a phase, or a KeyError naming the phases that have one."""
    try:
        return LISTS[phase]
    except KeyError:
        raise KeyError(f"{phase!r} has no checklist; the phases that do are {sorted(LISTS)}") from None


# The Deploy list under its original names, so everything written for Deploy first keeps working unchanged.
CHECKS = DEPLOY.checks
BY_ID = DEPLOY.by_id
GROUPS = DEPLOY.groups
GROUP_TITLE = DEPLOY.group_title
DECISION_ID = DEPLOY.decision_id


def of_group(group: str) -> tuple[Check, ...]:
    return DEPLOY.of_group(group)
