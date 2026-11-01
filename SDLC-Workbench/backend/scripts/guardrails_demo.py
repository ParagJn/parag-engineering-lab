"""See the guardrail scanner work, offline, and scan the real model output you already have on disk.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.guardrails_demo                       # planted fakes, offline
    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.guardrails_demo --recordings phase1  # YOUR recordings

The default run uses PLANTED FAKES, assembled from fragments inside this script (the repository is public, so no secret-shaped
text is ever written out whole). It shows each rule finding its fake with a rule name and a line number, an agent being told to
take a secret out, a person's edit refused, an email flagged and saved, and the approval record counting the flag.

--recordings NAME reads the replies saved under backend/recordings/NAME (gitignored), by your earlier live runs, and scans the
text of every model REPLY in them. It prints counts by rule and, for any finding, the file, the artefact and the line. It never
prints a value, a prompt or a reply. Exit 0 means nothing was found; exit 1 means something was, and I want to look at it with
you before the step closes. It makes no model call and needs no key.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from app.agents.runtime import AgentRuntime
from app.agents.reply import ReplyFormatError, parse_reply
from app.config import Settings, get_settings
from app.guardrails.scan import PERSONAL, SECRET, Scanner, counts_by_rule, describe
from app.llm.providers.mock import MockProvider
from app.llm.recordings import RecordingStore
from app.llm.types import ProviderResponse, Usage
from app.review.errors import EditRefused
from app.review.human import HumanActions

from .agent_demo import BRIEF, CHARTER, PERSON, POLICY
from .review_demo import MODELS, build as build_review

BANNER = (
    "*** PLANTED FAKES. Every secret and personal detail below was made up for this demo and assembled from fragments. ***\n"
    "*** Nothing here is real, and no value is ever printed: only the rule, the place and the length. ***"
)


def j(*parts: str) -> str:
    return "".join(parts)


FAKES = [
    ("private_key", j("-----", "BEGIN RSA PRIV", "ATE KEY-----")),
    ("aws_key_id", j("AK", "IA", "ABCDEFGHIJKLMNOP")),
    ("github_token", j("gh", "p_", "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8")),
    ("slack_token", j("xo", "xb-", "1234567890-abcdefghij")),
    ("stripe_key", j("sk", "_live_", "abcdefghijklmnop1234")),
    ("google_api_key", j("AI", "za", "SyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q")),
    ("jwt", j("ey", "Jhbgci0iJIUzI1", ".", "eyJzdWIiOiIxMjM0NTY3", ".", "SflKxwRJSMeKKF2QT4fw")),
    ("url_password", j("postgres", "://admin:", "Tr0ub4dor", "@db.internal:5432/app")),
    ("credential_assignment", j("api_key = ", "Zk9", "xQ2mP7", "vR4tY8wL")),
    ("email", j("contact ", "jane.doe", "@", "acme-corp.", "co.uk")),
    ("phone", "call +44 20 7946 0958"),
    ("payment_card", j("card ", "4111", " ", "1111", " ", "1111", " ", "1111")),
    ("iban", j("pay to ", "GB82", " WEST", " 1234", " 5698", " 7654", " 32")),
]
CONFIGURED = j("demo-own-", "ica-key-", "0001")
LEAKY_PERSONAS = j("- PER-001 Office staff member. Key ", "AK", "IA", "ABCDEFGHIJKLMNOP", ". Derives from: SET-CHR-001\n- PER-002 Room administrator. Derives from: SET-CHR-001")


def personas_reply(first_item: str) -> str:
    sections = {
        "Overview": "Two personas follow, taken from the charter [SET-CHR-001].", "Personas": first_item + "\n- PER-002 Room administrator, who keeps the list correct. Derives from: SET-CHR-001",
        "How the personas differ": "Staff book; the administrator maintains.", "Open questions": "How many rooms are there?",
    }
    return "<artefact>\n" + "\n".join(f"## {k}\n{v}" for k, v in sections.items()) + "\n</artefact>"


def where(f) -> str:
    return f"line {f.line}" + (f" under '{f.heading}'" if f.heading else "")


async def run_offline(workdir: Path) -> tuple[list[str], bool]:
    out: list[str] = []
    ok: list[bool] = []
    scanner = Scanner(secrets=[CONFIGURED])

    out.append("1. Each rule finds its planted fake (rule, class, where, length; never the value):")
    for rule, text in FAKES:
        [f] = [f for f in scanner.scan(f"## Notes\nan ordinary line\n{text}") if f.rule == rule] or [None]
        out.append(f"   {rule:22s} " + (f"{f.klass:8s} {where(f)}, {f.length} characters" if f else "NOT FOUND"))
        ok.append(f is not None and f.line == 3 and f.heading == "Notes")
    f = scanner.scan(f"see {CONFIGURED} here")
    out.append(f"   {'configured_credential':22s} " + (f"{f[0].klass:8s} {where(f[0])}, {f[0].length} characters   (the application's own key)" if f else "NOT FOUND"))
    ok.append(bool(f))

    clean = ["- FR-001 The system shall refuse a double booking. Derives from: PER-001 [DOC-001#1]", "Office hours are 08:00 to 18:00; v1.2.3; $0.01467; 1,395 tokens",
             "contact support@example.com", "password: ${DB_PASSWORD}", "the password policy requires twelve characters"]
    quiet = all(not scanner.scan(t) for t in clean)
    out.append(f"\n2. Ordinary artefact text (item IDs, citations, times, costs, example addresses, placeholders): {'nothing found' if quiet else 'SOMETHING FIRED'}")
    ok.append(quiet)

    settings = Settings(_env_file=None, data_dir=str(workdir / "data"), recordings_dir=str(workdir / "rec"), llm_retry_backoff_seconds=0,
                        ibm_ica_api_key=CONFIGURED, **{k: v for k, v in MODELS.items()})
    provider = MockProvider()
    store, runtime, reviews, human, engine, pid = build_review(workdir, settings, provider)
    store.artefacts.backstop = runtime.scanner
    store.context.scanner = runtime.scanner
    provider.queue("demo-sonnet", ProviderResponse(CHARTER, Usage(100, 100), "stop"))
    engine.start(pid, "setup", actor="system")
    await runtime.run(pid, "project_charter")
    engine.finish(pid, "setup", actor="system")
    engine.approve(pid, "setup", actor=PERSON)
    engine.start(pid, "requirements", actor="system")

    provider.queue("demo-sonnet", ProviderResponse(personas_reply(LEAKY_PERSONAS.split("\n")[0]), Usage(100, 100), "stop"),
                   ProviderResponse(personas_reply("- PER-001 Office staff member. Key withheld. Derives from: SET-CHR-001"), Usage(100, 100), "stop"))
    result = await runtime.run(pid, "personas")
    told = provider.calls[-1].request.messages[-1].content
    body = store.artefacts.get_version(pid, result.artefact_id).body
    out.append(f"\n3. An agent writes a secret into the personas: {result.attempts} attempt(s)")
    reason = next((l[2:] for l in told.splitlines() if "rule aws_key_id" in l), None)
    out.append("   the model was told: " + (reason or "NOTHING ABOUT A KEY (the scanner did not fire, so the secret was not caught)"))
    key = j("AK", "IA", "ABCDEFGHIJKLMNOP")
    instruction = told.split("could not be accepted", 1)[1].split("Write the complete corrected", 1)[0] if "could not be accepted" in told else ""
    leaked = key in body or key in instruction
    out.append(f"   saved version contains the key: {'YES (wrong)' if leaked else 'no'}; the instruction to the model contains the key: {'YES (wrong)' if leaked else 'no'}")
    ok.append(result.attempts == 2 and not leaked and reason is not None)

    admin = "\n- PER-002 Room administrator, who keeps the list correct. Derives from: SET-CHR-001"      # keep both items, as the ID rules require
    edit = ("## Overview\nTwo personas follow [SET-CHR-001].\n## Personas\n- PER-001 Office staff member, token " + j("gh", "p_", "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8")
            + ". Derives from: SET-CHR-001" + admin + "\n## How the personas differ\nStaff book.\n## Open questions\nNone.")
    try:
        human.edit(pid, "REQ-PER-001", edit, actor=PERSON)
        out.append("\n4. A person pastes a token into an edit: it was SAVED (wrong)")
        ok.append(False)
    except EditRefused as exc:
        shown = str(exc)
        rule = shown.split("rule ", 1)[1].split(")", 1)[0] if "rule " in shown else "refused for another reason, not by the scanner"
        out.append(f"\n4. A person pastes a token into an edit: refused, nothing saved ({rule}); the refusal repeats the token: "
                   f"{'YES (wrong)' if j('gh', 'p_') in shown else 'no'}")
        ok.append(rule == "github_token" and j("gh", "p_") not in shown and store.artefacts.get(pid, "REQ-PER-001").latest_version == 1)

    mail = j("jane.doe", "@", "acme-corp.", "co.uk")
    flagged = ("## Overview\nTwo personas follow [SET-CHR-001].\n## Personas\n- PER-001 Office staff member. Support contact " + mail
               + ". Derives from: SET-CHR-001" + admin + "\n## How the personas differ\nStaff book.\n## Open questions\nNone.")
    version = human.edit(pid, "REQ-PER-001", flagged, actor=PERSON)
    stored = store.artefacts.get_version(pid, "REQ-PER-001").generation["guardrails"]
    out.append(f"\n5. A person writes a support contact's email: saved as v{version}, flagged ({', '.join(f['rule'] for f in stored) or 'NOTHING FLAGGED'}"
               f"{' on line ' + str(stored[0]['line']) if stored else ''}); the flag holds the address: "
               f"{'YES (wrong)' if mail in json.dumps(stored) else 'no'}")
    ok.append(version == 2 and [f["rule"] for f in stored] == ["email"] and mail not in json.dumps(stored))

    for key, prefix, name in (("problem_statement", "REQ-PRB", "P"), ("vision_objectives", "REQ-VIS", "V"), ("functional_requirements", "REQ-F", "F"),
                              ("non_functional_requirements", "REQ-NF", "N"), ("epics_features", "REQ-EPC", "E")):
        store.artefacts.create(pid, artefact_type=key, phase_key="requirements", title=name, actor="system", prefix=prefix)
        store.artefacts.add_version(pid, f"{prefix}-001", body="placeholder", author=PERSON)
    engine.finish(pid, "requirements", actor="system")
    human.approve(pid, "requirements", actor=PERSON)
    detail = store.audit.list(pid, action="phase.decided")[-1].detail
    out.append(f"\n6. The approval record counts the flag, by artefact and rule: {detail['guardrail_flags']}")
    ok.append(detail["guardrail_flags"] == {"REQ-PER-001": {"email": 1}} and mail not in json.dumps(detail))

    doc = store.context.add_document(pid, "notes.md", f"# Notes\nbuild key {j('AK', 'IA', 'ABCDEFGHIJKLMNOP')}\n## Contacts\nask {mail}\n".encode(), actor=PERSON)
    out.append(f"\n7. A document is uploaded that contains a key and an email: accepted (document {doc.number}), flagged: "
               + ", ".join(f"{f.rule} ({where(f)})" for f in doc.findings))
    ok.append(doc.number > 0 and [f.rule for f in doc.findings] == ["aws_key_id", "email"])
    out[-1] = out[-1] if doc.findings else out[-1] + " NOTHING FLAGGED"
    return out, all(ok)


def scan_recordings(settings: Settings, name: str) -> tuple[list[str], int]:
    folder = settings.model_copy(update={"replay_set": name}).recordings_path
    lines: list[str] = []
    if not folder.is_dir():
        return [f"No recordings found for '{name}' (looked for the folder backend/recordings/{name})."], -1
    store = RecordingStore(folder)
    scanner = Scanner.from_settings(settings)
    findings_total = 0
    per_rule: dict[str, int] = {}
    rows = 0
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            reply = data["response"]["text"] if "response" in data else data.get("text", "")
            task = (data.get("request", {}).get("messages") or data.get("messages") or [["", ""]])[0]
            task_text = task["content"] if isinstance(task, dict) else task[1]
        except Exception:
            lines.append(f"  {path.name}: could not be read")
            continue
        m = re.search(r'Write the artefact "([^"]+)"|Review the artefact "([^"]+)"', task_text)
        label = (m.group(1) or f"review of {m.group(2)}") if m else "(unknown)"
        try:
            body = parse_reply(reply)
        except ReplyFormatError:
            body = reply
        found = scanner.scan(body)
        rows += 1
        for f in found:
            findings_total += 1
            per_rule[f.rule] = per_rule.get(f.rule, 0) + 1
            lines.append(f"  {path.name} ({label}): {f.rule} [{f.klass}] {where(f)}, {f.length} characters")
    lines.insert(0, f"Scanned {rows} recorded reply(ies) in recordings/{name} with all {len(scanner.active_rules())} active rules"
                    + (f" ({len(store)} loaded by the replay store)." if len(store) != rows else "."))
    lines.append(f"Findings: {findings_total}" + (f"   by rule: {dict(sorted(per_rule.items()))}" if per_rule else "   (none)"))
    return lines, findings_total


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--recordings", metavar="NAME", help="scan the replies in backend/recordings/NAME instead (counts only; no model call)")
    args = parser.parse_args(argv)
    if args.recordings is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.recordings):
        parser.error("a recording name is letters, digits, '-' and '_' only, up to 64 characters")

    if args.recordings:
        cfg = settings or get_settings()
        lines, total = scan_recordings(cfg, args.recordings)
        print("\n".join(lines))
        if total < 0:
            return 2
        print("\n" + ("Nothing found in your real model output." if total == 0 else "Something was found. Do not close the step yet; it needs a look to decide whether it is real or a false positive."))
        return 0 if total == 0 else 1

    with tempfile.TemporaryDirectory(prefix="sdlc_guardrails_demo_") as tmp:
        lines, passed = asyncio.run(run_offline(Path(tmp)))
    print(BANNER + "\n")
    print("\n".join(lines))
    print("\n" + ("everything behaved as specified" if passed else "SOMETHING DID NOT BEHAVE AS SPECIFIED, see above"))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
