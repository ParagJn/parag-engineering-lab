"""Session repository backed by SQLite (see app/db.py)."""

from datetime import datetime
from typing import Optional

from ..db import Database, get_database
from ..models import Message, MessageAttachment, Session

# Message fields that may change after a message is saved; compared on update
_MUTABLE_MESSAGE_FIELDS = ("role", "content", "svg_image_id", "svg_parent_id", "svg_version")


class SessionRepository:
    """Repository for session persistence."""

    def __init__(self, db: Optional[Database] = None):
        """Initialize repository."""
        self.db = db or get_database()

    def create(self, session: Session) -> Session:
        """Create a new session (and any messages it already has)."""
        with self.db.transaction():
            if self.db.exists("sessions", {"session_id": session.session_id}):
                raise ValueError(f"Session {session.session_id} already exists")
            self.db.insert("sessions", self._session_row(session))
            self._sync_messages(session)
        return session

    def get(self, session_id: str) -> Optional[Session]:
        """Get a session by ID, with its messages in order."""
        row = self.db.get("sessions", {"session_id": session_id})
        if not row:
            return None
        attachment_ids = [
            r["attachment_id"]
            for r in self.db.find("attachments", {"session_id": session_id}, order_by="created_at")
        ]
        return self._to_session(row, self._load_messages(session_id), attachment_ids)

    def list_all(self) -> list[Session]:
        """
        List all sessions, most recently updated first.

        For speed the sessions come back without their messages or
        attachment IDs; use get() for a full session.
        """
        rows = self.db.find("sessions", order_by="updated_at DESC")
        return [self._to_session(row, [], []) for row in rows]

    def update(self, session: Session) -> Session:
        """Save a session: its fields, new messages, and removed messages."""
        session.updated_at = datetime.utcnow()

        with self.db.transaction():
            row = self._session_row(session)
            row.pop("session_id")
            row.pop("created_at")
            if not self.db.update("sessions", {"session_id": session.session_id}, row):
                raise ValueError(f"Session {session.session_id} does not exist")
            self._sync_messages(session)
        return session

    def delete(self, session_id: str) -> bool:
        """
        Delete a session and its messages.

        Uploaded files stay on disk and in the attachments table (their
        session link is cleared), same as before the move to SQLite.
        """
        return self.db.delete("sessions", {"session_id": session_id}) > 0

    # ------------------------------------------------------------------ helpers

    def _sync_messages(self, session: Session):
        """Make the stored messages match session.messages (call inside a transaction)."""
        existing = {
            row["id"]: row
            for row in self.db.query(
                "SELECT id, role, content, svg_image_id, svg_parent_id, svg_version "
                "FROM messages WHERE session_id = ?",
                [session.session_id],
            )
        }

        for message in session.messages:
            row = self._message_row(session.session_id, message)
            stored = existing.pop(message.id, None)
            if stored is None:
                self.db.insert("messages", row)
                self._link_attachments(message)
            else:
                changes = {f: row[f] for f in _MUTABLE_MESSAGE_FIELDS if stored[f] != row[f]}
                if changes:
                    self.db.update("messages", {"id": message.id}, changes)

        # Anything left was removed from the session (e.g. a failed turn)
        if existing:
            self.db.delete("messages", {"id": list(existing)})

    def _link_attachments(self, message: Message):
        """Record which files a message was sent with (skips files that aren't in the database)."""
        for position, attachment in enumerate(message.attachments):
            self.db.execute(
                "INSERT OR IGNORE INTO message_attachments (message_id, attachment_id, position) "
                "SELECT ?, ?, ? WHERE EXISTS (SELECT 1 FROM attachments WHERE attachment_id = ?)",
                [message.id, attachment.attachment_id, position, attachment.attachment_id],
            )

    def _load_messages(self, session_id: str) -> list[Message]:
        attachments: dict[str, list[MessageAttachment]] = {}
        for row in self.db.query(
            "SELECT ma.message_id, a.attachment_id, a.filename, a.mime_type "
            "FROM message_attachments ma "
            "JOIN messages m ON m.id = ma.message_id "
            "JOIN attachments a ON a.attachment_id = ma.attachment_id "
            "WHERE m.session_id = ? ORDER BY ma.position",
            [session_id],
        ):
            attachments.setdefault(row["message_id"], []).append(
                MessageAttachment(
                    attachment_id=row["attachment_id"],
                    filename=row["filename"],
                    mime_type=row["mime_type"],
                )
            )

        return [
            Message(
                id=row["id"],
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"],
                attachments=attachments.get(row["id"], []),
                svg_image_id=row["svg_image_id"],
                svg_parent_id=row["svg_parent_id"],
                svg_version=row["svg_version"],
            )
            for row in self.db.find("messages", {"session_id": session_id}, order_by="pk")
        ]

    @staticmethod
    def _to_session(row: dict, messages: list[Message], attachment_ids: list[str]) -> Session:
        return Session(
            session_id=row["session_id"],
            project_id=row["project_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            title=row["title"],
            model=row["model"],
            web_search_enabled=row["web_search_enabled"],
            messages=messages,
            attachment_ids=attachment_ids,
        )

    @staticmethod
    def _session_row(session: Session) -> dict:
        return {
            "session_id": session.session_id,
            "project_id": session.project_id,
            "title": session.title,
            "model": session.model,
            "web_search_enabled": session.web_search_enabled,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }

    @staticmethod
    def _message_row(session_id: str, message: Message) -> dict:
        role = message.role.value if hasattr(message.role, "value") else message.role
        return {
            "id": message.id,
            "session_id": session_id,
            "role": role,
            "content": message.content,
            "created_at": message.created_at,
            "svg_image_id": message.svg_image_id,
            "svg_parent_id": message.svg_parent_id,
            "svg_version": message.svg_version,
        }
