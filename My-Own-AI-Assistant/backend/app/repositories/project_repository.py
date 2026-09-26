"""Project repository backed by SQLite (see app/db.py)."""

from datetime import datetime
from typing import Optional

from ..db import Database, get_database
from ..models import Attachment, Project
from .attachment_repository import AttachmentRepository


class ProjectRepository:
    """Repository for projects and their pinned documents."""

    def __init__(self, db: Optional[Database] = None):
        """Initialize repository."""
        self.db = db or get_database()

    def create(self, project: Project) -> Project:
        """Create a new project."""
        self.db.insert("projects", self._row(project))
        return project

    def get(self, project_id: str) -> Optional[Project]:
        """Get a project by ID."""
        row = self.db.get("projects", {"project_id": project_id})
        return Project(**row) if row else None

    def list_all(self) -> list[Project]:
        """All projects, alphabetically."""
        return [Project(**row) for row in self.db.find("projects", order_by="name")]

    def update(self, project: Project) -> Project:
        """Save a project's fields."""
        project.updated_at = datetime.utcnow()
        row = self._row(project)
        row.pop("project_id")
        row.pop("created_at")
        if not self.db.update("projects", {"project_id": project.project_id}, row):
            raise ValueError(f"Project {project.project_id} does not exist")
        return project

    def delete(self, project_id: str) -> bool:
        """Delete a project. Its chats stay (their project is cleared) and its pins are removed."""
        return self.db.delete("projects", {"project_id": project_id}) > 0

    def touch(self, project_id: str):
        """Bump updated_at, e.g. after its documents change."""
        self.db.update("projects", {"project_id": project_id}, {"updated_at": datetime.utcnow()})

    # --------------------------------------------------------------- documents

    def list_documents(self, project_id: str) -> list[Attachment]:
        """Documents pinned to a project, in the order they were pinned."""
        rows = self.db.query(
            "SELECT a.* FROM project_documents pd "
            "JOIN attachments a ON a.attachment_id = pd.attachment_id "
            "WHERE pd.project_id = ? ORDER BY pd.pinned_at",
            [project_id],
        )
        return [AttachmentRepository.from_row(self.db._decode("attachments", row)) for row in rows]

    def pin_document(self, project_id: str, attachment_id: str) -> bool:
        """Pin a document. Returns False if it was already pinned."""
        return self.db.insert(
            "project_documents",
            {"project_id": project_id, "attachment_id": attachment_id, "pinned_at": datetime.utcnow()},
            or_ignore=True,
        ) > 0

    def unpin_document(self, project_id: str, attachment_id: str) -> bool:
        """Unpin a document. Returns False if it wasn't pinned."""
        return self.db.delete(
            "project_documents", {"project_id": project_id, "attachment_id": attachment_id}
        ) > 0

    def is_document_in_use(self, attachment_id: str) -> bool:
        """True if a file is still used anywhere: a chat, a sent message, or a project pin."""
        if self.db.exists("project_documents", {"attachment_id": attachment_id}):
            return True
        if self.db.exists("message_attachments", {"attachment_id": attachment_id}):
            return True
        row = self.db.get("attachments", {"attachment_id": attachment_id})
        return bool(row and row["session_id"])

    # ------------------------------------------------------------------- stats

    def session_counts(self) -> dict[str, int]:
        """Number of chats in each project."""
        rows = self.db.query(
            "SELECT project_id, COUNT(*) AS n FROM sessions WHERE project_id IS NOT NULL GROUP BY project_id"
        )
        return {row["project_id"]: row["n"] for row in rows}

    def session_ids(self, project_id: str) -> list[str]:
        """IDs of the chats in a project."""
        return [row["session_id"] for row in self.db.find("sessions", {"project_id": project_id})]

    @staticmethod
    def _row(project: Project) -> dict:
        return {
            "project_id": project.project_id,
            "name": project.name,
            "description": project.description,
            "instructions": project.instructions,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
        }
