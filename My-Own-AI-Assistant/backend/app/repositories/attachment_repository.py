"""Attachment repository: metadata in SQLite (see app/db.py), files on disk."""

import shutil
from pathlib import Path
from typing import Optional

from ..config import config
from ..db import Database, get_database
from ..models import Attachment


def to_stored_path(path: str | Path | None) -> Optional[str]:
    """Store paths under the data folder relative to it, so moving the project doesn't break them."""
    if path is None:
        return None
    path = Path(path)
    try:
        return path.resolve().relative_to(config.DATA_DIR.resolve()).as_posix()
    except ValueError:
        return str(path)


def from_stored_path(path: str | None) -> Optional[str]:
    """Turn a stored path back into an absolute one."""
    if path is None:
        return None
    return str(Path(path) if Path(path).is_absolute() else config.DATA_DIR / path)


class AttachmentRepository:
    """Repository for attachment persistence."""

    def __init__(self, documents_dir: Optional[Path] = None, db: Optional[Database] = None):
        """Initialize repository."""
        self.documents_dir = documents_dir or config.DOCUMENTS_DIR
        self.documents_dir.mkdir(parents=True, exist_ok=True)
        self.db = db or get_database()

    def _get_attachment_dir(self, attachment_id: str) -> Path:
        """Get directory for attachment."""
        return self.documents_dir / attachment_id

    def create(self, attachment: Attachment) -> Attachment:
        """Create a new attachment record."""
        self._get_attachment_dir(attachment.attachment_id).mkdir(parents=True, exist_ok=True)
        self.db.insert("attachments", self.to_row(attachment))
        return attachment

    def get(self, attachment_id: str) -> Optional[Attachment]:
        """Get attachment by ID."""
        row = self.db.get("attachments", {"attachment_id": attachment_id})
        return self.from_row(row) if row else None

    def list_for_session(self, session_id: str) -> list[Attachment]:
        """Attachments uploaded in a chat, oldest first."""
        rows = self.db.find("attachments", {"session_id": session_id}, order_by="created_at")
        return [self.from_row(row) for row in rows]

    def update(self, attachment: Attachment) -> Attachment:
        """Update attachment metadata."""
        row = self.to_row(attachment)
        row.pop("attachment_id")
        if not self.db.update("attachments", {"attachment_id": attachment.attachment_id}, row):
            raise ValueError(f"Attachment {attachment.attachment_id} does not exist")
        return attachment

    def delete(self, attachment_id: str) -> bool:
        """Delete an attachment record and its files."""
        deleted = self.db.delete("attachments", {"attachment_id": attachment_id}) > 0

        attachment_dir = self._get_attachment_dir(attachment_id)
        if attachment_dir.exists():
            shutil.rmtree(attachment_dir)
            deleted = True
        return deleted

    def get_file_path(self, attachment_id: str, filename: str) -> Path:
        """Get path to store a file."""
        return self._get_attachment_dir(attachment_id) / filename

    def get_content_markdown_path(self, attachment_id: str) -> Path:
        """Get path for content markdown."""
        return self._get_attachment_dir(attachment_id) / "content.md"

    def get_image_path(self, attachment_id: str, image_filename: str) -> Path:
        """Get path to store an extracted image."""
        return self._get_attachment_dir(attachment_id) / "images" / image_filename

    # ------------------------------------------------------------------ mapping

    @staticmethod
    def to_row(attachment: Attachment) -> dict:
        """Attachment -> database row (paths stored relative to the data folder)."""
        images = []
        for image in attachment.images:
            image_data = image.model_dump(mode="json")
            image_data["stored_path"] = to_stored_path(image.stored_path)
            images.append(image_data)
        status = attachment.status.value if hasattr(attachment.status, "value") else attachment.status
        return {
            "attachment_id": attachment.attachment_id,
            "session_id": attachment.session_id,
            "filename": attachment.filename,
            "mime_type": attachment.mime_type,
            "size_bytes": attachment.size_bytes,
            "stored_path": to_stored_path(attachment.stored_path),
            "content_markdown_path": to_stored_path(attachment.content_markdown_path),
            "images": images,
            "status": status,
            "created_at": attachment.created_at,
        }

    @staticmethod
    def from_row(row: dict) -> Attachment:
        """Database row -> Attachment (paths made absolute again)."""
        images = [
            {**image, "stored_path": from_stored_path(image.get("stored_path"))}
            for image in row["images"]
        ]
        return Attachment(
            attachment_id=row["attachment_id"],
            session_id=row["session_id"],
            filename=row["filename"],
            mime_type=row["mime_type"],
            size_bytes=row["size_bytes"],
            created_at=row["created_at"],
            stored_path=from_stored_path(row["stored_path"]),
            content_markdown_path=from_stored_path(row["content_markdown_path"]),
            images=images,
            status=row["status"],
        )
