"""BAU handover, offline and free (S22b): a runbook and a hypercare plan made from a small written-out sample, saved as Markdown and as Word files in a temporary
folder that is printed, so you can open the .docx files in Word and look at them.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.handover_demo

No model is called, nothing is sent anywhere, and nothing outside the temporary folder is written. The text is a fixed sample, NOT how a real model writes.
Every number in it is marked "Proposed:", the way the real skills ask for.
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.deploy.docx_writer import DocInfo, markdown_to_docx

RUNBOOK = """# Runbook

## Overview
This runbook was written from the approved design, the deployment plan and the release notes, **not** from the running product, which is built and run outside this tool. It covers the *Meeting Room Booking* service [COMP-001] and its data store [COMP-002].

## Routine care
- RUN-001 Check that the room list page opens. Done by the support person each morning (*Proposed: daily*); it is fine when the rooms appear within a few seconds. Derives from: COMP-001, NFR-002
- RUN-002 Check that a new booking can be saved and then seen. Done by the support person once a week (*Proposed: weekly*); it is fine when the booking appears in the list. Derives from: COMP-001, COMP-002

## Starting and stopping
1. Start the data store first (deployment step DPL-001), then the booking service (DPL-002).
2. Stop them in the opposite order. Each is up when the room list page opens.

## When something goes wrong
- RUN-003 The room list does not open. It probably means the booking service is not answering. First restart it as in DPL-002; if it still does not open, check the data store. Derives from: COMP-001
- RUN-004 A booking does not save. It probably means the data store is not answering. Check that it is up (DPL-001); if it is, tell the people who built the product. Derives from: COMP-002

## Recovery and rollback
Follow the rollback in the deployment plan. Bookings made after the release are lost on rollback; the BAU lead decides, and tells the staff first.

## Contacts and tools
| Question | Answer |
|---|---|
| Who is on call? | *To be supplied by the support team* |
| Where do alerts go? | *To be supplied by the support team* |
| Where are logs kept? | *To be supplied by the support team* |

## Coverage check
None

## Open questions
- How often should the routine checks run? The entries propose daily and weekly.
- Who is on call, and how are they reached?
"""

HYPERCARE = """# Hypercare plan

## Overview
Hypercare is the extra support in the first weeks after go-live. This plan was written from the design and the runbook, not from the running product. Every length and number below is a **proposal** until the support team agrees it.

## Who is on hand
- HYP-001 Someone who can fix the product when it breaks. *Proposed: office hours, first two weeks.* Derives from: NFR-001
- HYP-002 Someone who answers staff questions about booking. *Proposed: office hours, first two weeks.* Derives from: NFR-002

## What is watched
- The room list opening (runbook entry RUN-001), *Proposed: every morning*.
- Bookings being saved (runbook entry RUN-002), *Proposed: twice a week*.

## Escalation
1. The support person tries the first action in the runbook entry (RUN-003 or RUN-004).
2. If that does not help, they tell the people who built the product. *Proposed: within one working day.*

## Exit criteria
- No serious problem has been open for the agreed period.
- The room list opened every day that it was checked.

## Coverage check
None

## Open questions
- How many weeks should hypercare last? This plan proposes two.
- Who decides that hypercare may end?
"""


def main() -> None:
    when = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory(prefix="handover_demo_", delete=False) as tmp:
        folder = Path(tmp)
        for name, text, title in (("HND-RUN-001-v1", RUNBOOK, "Runbook - Meeting Room Booking"), ("HND-HYP-001-v1", HYPERCARE, "Hypercare plan - Meeting Room Booking")):
            (folder / f"{name}.md").write_text(text, encoding="utf-8")
            (folder / f"{name}.docx").write_bytes(markdown_to_docx(text, DocInfo(title=title, subject=name, created=when)))
        print("SAMPLE TEXT, NOT A REAL MODEL'S WRITING. Files written to:\n")
        for path in sorted(folder.iterdir()):
            print(f"  {path}  ({path.stat().st_size:,} bytes)")
        print("\nOpen the .docx files in Word to see headings, lists, the table and the proposal wording as the downloads will look.")


if __name__ == "__main__":
    main()
