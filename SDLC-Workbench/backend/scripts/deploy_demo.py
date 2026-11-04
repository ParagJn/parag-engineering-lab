"""Deploy, offline and free (S21b): a deployment plan and release notes made from a small written-out sample, saved as Markdown and as Word files in a temporary folder
that is printed, so you can open the .docx files in Word and look at them.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.deploy_demo

No model is called, nothing is sent anywhere, and nothing outside the temporary folder is written. The text is a fixed sample, NOT how a real model writes.
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.deploy.docx_writer import DocInfo, markdown_to_docx

PLAN = """# Deployment plan

## Overview
This plan was written from the approved design and **not** from the code, which is built outside this tool. It covers the *Meeting Room Booking* service [COMP-001] and the room list [COMP-002].

## Environments
- A **test** place, where the release is tried first.
- A **live** place, which the staff use.

## Steps
- DPL-001 Create the data store before anything else. Done by the release owner; it worked when the rooms and bookings tables exist. Derives from: COMP-001, COMP-002
- DPL-002 Start the booking service. Done by the release owner after DPL-001; it worked when the room list page opens. Derives from: COMP-001

## Configuration and secrets
| Setting | What it is for | Where it is kept |
|---|---|---|
| `DATABASE_LOCATION` | Where the data store is | In the place the team keeps secrets |
| `SESSION_SECRET` | Signs people in | In the place the team keeps secrets |

Values are never written in this plan.

## Data and migrations
The rooms and bookings tables are created at release. Nothing existing is changed.

## Rollback
1. Stop the booking service.
2. Restore the data store from the backup taken before DPL-001.
3. Start the previous version, if there is one.

> Anything bookings made after the release is lost on rollback. The owner decides, and says so to the staff first.

## Coverage check
None

## Open questions
- Which place is "live"? The design does not say.
"""

NOTES = """# Release notes

## Overview
This is the first release of Meeting Room Booking. These notes describe what the design promises; they were written before the product was checked against it.

## What is new
- REL-001 You can book a meeting room for a time that suits you. Derives from: FR-001
- REL-002 You can cancel a booking you made. Derives from: FR-002

## Known limits
- Bookings cannot be moved to another room; cancel and book again.

## Upgrade notes
This is the first release.

## Coverage check
None

## Open questions
- What should the release be called?
"""


def main() -> None:
    when = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory(prefix="deploy_demo_", delete=False) as tmp:
        folder = Path(tmp)
        for name, text, title in (("DEP-PLN-001-v1", PLAN, "Deployment plan - Meeting Room Booking"), ("DEP-REL-001-v1", NOTES, "Release notes - Meeting Room Booking")):
            (folder / f"{name}.md").write_text(text, encoding="utf-8")
            (folder / f"{name}.docx").write_bytes(markdown_to_docx(text, DocInfo(title=title, subject=name, created=when)))
        print("SAMPLE TEXT, NOT A REAL MODEL'S WRITING. Files written to:\n")
        for path in sorted(folder.iterdir()):
            print(f"  {path}  ({path.stat().st_size:,} bytes)")
        print("\nOpen the .docx files in Word to see headings, lists, the table, the quote and the code-style text as the downloads will look.")


if __name__ == "__main__":
    main()
