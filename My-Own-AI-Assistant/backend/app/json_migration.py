"""One-time import of the old JSON data into SQLite.

Reads data/sessions/*.json and data/documents/*/metadata.json and writes them
into data/assistant.db. The JSON files are backed up first and never modified
or deleted. Safe to run more than once: anything already imported is skipped.

Runs automatically on startup until it has completed once without errors.
To run it by hand (from the backend folder):

    python -m app.json_migration --dry-run   # import into a throwaway copy, report only
    python -m app.json_migration             # import for real
"""

import argparse
import json
import logging
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import config
from .db import Database, get_database
from .models import Attachment, Session
from .repositories.attachment_repository import AttachmentRepository
from .repositories.session_repository import SessionRepository

logger = logging.getLogger(__name__)

IMPORT_MARKER = "json_import_completed_at"


@dataclass
class MigrationReport:
    """What the import found and did."""
    sessions_found: int = 0
    sessions_imported: int = 0
    sessions_skipped: int = 0
    messages_found: int = 0
    messages_in_db: int = 0
    attachments_found: int = 0
    attachments_imported: int = 0
    attachments_skipped: int = 0
    attachments_without_chat: list[str] = field(default_factory=list)
    missing_attachments: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    backup_dir: Optional[Path] = None

    def summary(self) -> str:
        lines = [
            f"Chats:    {self.sessions_found} found, {self.sessions_imported} imported, "
            f"{self.sessions_skipped} already in the database",
            f"Messages: {self.messages_found} in JSON, {self.messages_in_db} now in the database for those chats",
            f"Files:    {self.attachments_found} found, {self.attachments_imported} imported, "
            f"{self.attachments_skipped} already in the database",
        ]
        if self.backup_dir:
            lines.append(f"Backup of the JSON files: {self.backup_dir}")
        if self.attachments_without_chat:
            lines.append(
                f"{len(self.attachments_without_chat)} file(s) were uploaded but never sent in a chat; "
                f"imported without a chat link: {', '.join(self.attachments_without_chat)}"
            )
        if self.missing_attachments:
            lines.append(
                f"{len(self.missing_attachments)} file reference(s) in messages point to files with no "
                f"metadata.json; those file chips won't show: {', '.join(self.missing_attachments)}"
            )
        if self.errors:
            lines.append(f"{len(self.errors)} error(s):")
            lines.extend(f"  - {error}" for error in self.errors)
        else:
            lines.append("No errors.")
        return "\n".join(lines)


def backup_json_files(backups_dir: Optional[Path] = None) -> Optional[Path]:
    """Copy sessions/*.json and every documents/*/metadata.json into a timestamped folder."""
    session_files = sorted(config.SESSIONS_DIR.glob("*.json"))
    metadata_files = sorted(config.DOCUMENTS_DIR.glob("*/metadata.json"))
    if not session_files and not metadata_files:
        return None

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = (backups_dir or config.DATA_DIR / "backups") / f"json-{stamp}"
    for source in session_files + metadata_files:
        dest = target / source.relative_to(config.DATA_DIR)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    return target


def import_json(db: Database, backup: bool = True) -> MigrationReport:
    """Import all JSON sessions and attachment metadata into `db`."""
    report = MigrationReport()
    if backup:
        report.backup_dir = backup_json_files()

    session_repository = SessionRepository(db=db)

    # Load everything first: a file's chat comes from the first message that used it
    sessions: list[Session] = []
    for path in sorted(config.SESSIONS_DIR.glob("*.json")):
        report.sessions_found += 1
        try:
            with open(path, "r", encoding="utf-8") as f:
                sessions.append(Session(**json.load(f)))
        except Exception as e:
            report.errors.append(f"{path.name}: could not read ({e})")

    attachments: dict[str, Attachment] = {}
    for path in sorted(config.DOCUMENTS_DIR.glob("*/metadata.json")):
        report.attachments_found += 1
        try:
            with open(path, "r", encoding="utf-8") as f:
                attachment = Attachment(**json.load(f))
            attachments[attachment.attachment_id] = attachment
        except Exception as e:
            report.errors.append(f"{path.parent.name}/metadata.json: could not read ({e})")

    first_used_in: dict[str, str] = {}
    for session in sorted(sessions, key=lambda s: s.created_at):
        for message in session.messages:
            for ref in message.attachments:
                first_used_in.setdefault(ref.attachment_id, session.session_id)
                if ref.attachment_id not in attachments and ref.attachment_id not in report.missing_attachments:
                    report.missing_attachments.append(ref.attachment_id)

    # Sessions first (attachments point at them), then attachments, then the
    # message -> file links (which need both)
    for session in sessions:
        report.messages_found += len(session.messages)
        if db.exists("sessions", {"session_id": session.session_id}):
            report.sessions_skipped += 1
            continue
        try:
            with db.transaction():
                db.insert("sessions", SessionRepository._session_row(session))
                for message in session.messages:
                    db.insert(
                        "messages",
                        SessionRepository._message_row(session.session_id, message),
                        or_ignore=True,
                    )
            report.sessions_imported += 1
        except Exception as e:
            report.errors.append(f"chat {session.session_id}: could not import ({e})")

    for attachment_id, attachment in attachments.items():
        if db.exists("attachments", {"attachment_id": attachment_id}):
            report.attachments_skipped += 1
            continue
        session_id = first_used_in.get(attachment_id)
        if session_id and not db.exists("sessions", {"session_id": session_id}):
            session_id = None
        if not session_id:
            report.attachments_without_chat.append(attachment_id)
        attachment.session_id = session_id
        try:
            db.insert("attachments", AttachmentRepository.to_row(attachment))
            report.attachments_imported += 1
        except Exception as e:
            report.errors.append(f"file {attachment_id}: could not import ({e})")

    for session in sessions:
        try:
            with db.transaction():
                for message in session.messages:
                    session_repository._link_attachments(message)
        except Exception as e:
            report.errors.append(f"chat {session.session_id}: could not link files ({e})")

    # Verify: every JSON message should now be in the database
    ids = [s.session_id for s in sessions]
    if ids:
        report.messages_in_db = db.count("messages", {"session_id": ids})
    if report.messages_in_db < report.messages_found:
        report.errors.append(
            f"only {report.messages_in_db} of {report.messages_found} messages are in the database"
        )

    if not report.errors:
        db.upsert("app_meta", {"key": IMPORT_MARKER, "value": datetime.utcnow().isoformat()}, "key")
    return report


def import_json_if_needed(db: Optional[Database] = None) -> Optional[MigrationReport]:
    """Startup hook: run the import unless it has already completed once."""
    db = db or get_database()
    if db.exists("app_meta", {"key": IMPORT_MARKER}):
        return None

    has_json = any(config.SESSIONS_DIR.glob("*.json")) or any(config.DOCUMENTS_DIR.glob("*/metadata.json"))
    if not has_json:
        db.upsert("app_meta", {"key": IMPORT_MARKER, "value": datetime.utcnow().isoformat()}, "key")
        return None

    logger.info("Importing JSON chats and files into SQLite (one time)...")
    report = import_json(db)
    for line in report.summary().splitlines():
        (logger.warning if report.errors else logger.info)("JSON import: %s", line)
    if report.errors:
        logger.warning("JSON import: will retry on next startup; the JSON files are untouched.")
    return report


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Import the old JSON chats and files into SQLite.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="import into a throwaway copy of the database and only print the report",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        with tempfile.TemporaryDirectory() as tmp:
            temp_path = Path(tmp) / "dry-run.db"
            if config.DB_PATH.exists():
                live = Database(config.DB_PATH)
                live.backup(temp_path)
                live.close()
            db = Database(temp_path)
            report = import_json(db, backup=False)
            db.close()
        print("DRY RUN - nothing was written to", config.DB_PATH)
    else:
        report = import_json(get_database())

    print(report.summary())
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
