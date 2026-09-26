"""Project service: projects, their pinned documents, and the context they add to chats."""

import math
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..config import config
from ..models import Attachment, AttachmentStatus, Project
from ..repositories import ProjectRepository, SessionRepository
from .attachment_service import AttachmentService, get_attachment_service


class ProjectBudgetError(ValueError):
    """Raised when pinning a document would push a project over its context budget."""
    pass


@dataclass
class ProjectDocument:
    """A pinned document and its estimated size in the prompt."""
    attachment: Attachment
    tokens: int


@dataclass
class ProjectContext:
    """What a project adds to the system prompt of its chats."""
    project: Project
    instructions: str
    documents_context: Optional[str]
    document_count: int


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token). Good enough for a budget, not exact."""
    return math.ceil(len(text) / 4)


class ProjectService:
    """Service for project management."""

    def __init__(
        self,
        repository: Optional[ProjectRepository] = None,
        session_repository: Optional[SessionRepository] = None,
        attachment_service: Optional[AttachmentService] = None,
    ):
        """Initialize project service."""
        self.repository = repository or ProjectRepository()
        self.session_repository = session_repository or SessionRepository()
        self.attachment_service = attachment_service or get_attachment_service()

    # ----------------------------------------------------------------- projects

    def create_project(self, name: str, description: str = "", instructions: str = "") -> Project:
        """Create a new project."""
        now = datetime.utcnow()
        project = Project(
            project_id=f"proj_{uuid.uuid4().hex[:16]}",
            name=self._clean_name(name),
            description=description.strip(),
            instructions=instructions.strip(),
            created_at=now,
            updated_at=now,
        )
        return self.repository.create(project)

    def get_project(self, project_id: str) -> Optional[Project]:
        """Get a project by ID."""
        return self.repository.get(project_id)

    def list_projects(self) -> list[Project]:
        """All projects, alphabetically."""
        return self.repository.list_all()

    def update_project(
        self,
        project: Project,
        name: Optional[str] = None,
        description: Optional[str] = None,
        instructions: Optional[str] = None,
    ) -> Project:
        """Change a project's name, description and/or instructions."""
        if name is not None:
            project.name = self._clean_name(name)
        if description is not None:
            project.description = description.strip()
        if instructions is not None:
            project.instructions = instructions.strip()
        return self.repository.update(project)

    def delete_project(self, project_id: str, delete_chats: bool = False) -> bool:
        """
        Delete a project.

        By default its chats are kept and just leave the project. With
        delete_chats=True they are deleted too. Pinned files that nothing else
        uses any more (no chat, no message, no other project) are deleted.
        """
        document_ids = [d.attachment_id for d in self.repository.list_documents(project_id)]
        with self.repository.db.transaction():
            if delete_chats:
                for session_id in self.repository.session_ids(project_id):
                    self.session_repository.delete(session_id)
            deleted = self.repository.delete(project_id)
        if deleted:
            for attachment_id in document_ids:
                self._delete_file_if_unused(attachment_id)
        return deleted

    # ---------------------------------------------------------------- documents

    def list_documents(self, project_id: str) -> list[ProjectDocument]:
        """Pinned documents with their estimated token counts."""
        return [
            ProjectDocument(attachment=a, tokens=self._document_tokens(a.attachment_id))
            for a in self.repository.list_documents(project_id)
        ]

    def context_tokens(self, project_id: str) -> int:
        """Estimated tokens the project's documents add to every message."""
        return sum(d.tokens for d in self.list_documents(project_id))

    def pin_document(self, project_id: str, attachment_id: str) -> ProjectDocument:
        """
        Pin a processed file to a project.

        Refuses (never truncates) a file that would push the project over
        PROJECT_CONTEXT_MAX_TOKENS, since a silently cut document leads to
        wrong answers about the missing part.
        """
        attachment = self.attachment_service.get_attachment(attachment_id)
        if not attachment:
            raise LookupError("File not found")

        status = getattr(attachment.status, "value", attachment.status)
        if status != AttachmentStatus.READY.value:
            raise ValueError(f"'{attachment.filename}' could not be read (status: {status}), so it can't be pinned")

        content = self.attachment_service.get_attachment_content(attachment_id)
        if not content or not content.strip():
            raise ValueError(f"No text could be extracted from '{attachment.filename}', so it can't be pinned")

        documents = self.list_documents(project_id)
        existing = next((d for d in documents if d.attachment.attachment_id == attachment_id), None)
        if existing:
            return existing

        tokens = estimate_tokens(content)
        used = sum(d.tokens for d in documents)
        budget = config.PROJECT_CONTEXT_MAX_TOKENS
        if used + tokens > budget:
            raise ProjectBudgetError(
                f"'{attachment.filename}' is about {tokens:,} tokens. The project already uses about "
                f"{used:,} of its {budget:,} token budget, so it doesn't fit. Remove a document "
                f"or attach this one to a single message instead."
            )

        self.repository.pin_document(project_id, attachment_id)
        self.repository.touch(project_id)
        return ProjectDocument(attachment=attachment, tokens=tokens)

    def unpin_document(self, project_id: str, attachment_id: str) -> bool:
        """Unpin a file, and delete it if nothing else uses it."""
        removed = self.repository.unpin_document(project_id, attachment_id)
        if removed:
            self.repository.touch(project_id)
            self._delete_file_if_unused(attachment_id)
        return removed

    # ------------------------------------------------------------------ context

    def build_context(self, project_id: Optional[str]) -> Optional[ProjectContext]:
        """Instructions and document text a project adds to its chats' system prompt."""
        if not project_id:
            return None
        project = self.repository.get(project_id)
        if not project:
            return None

        parts = []
        for attachment in self.repository.list_documents(project_id):
            content = self.attachment_service.get_attachment_content(attachment.attachment_id)
            if content:
                parts.append(
                    f"<project_document id='{attachment.attachment_id}' filename='{attachment.filename}'>\n"
                    f"{content}\n</project_document>"
                )

        return ProjectContext(
            project=project,
            instructions=project.instructions,
            documents_context="\n\n".join(parts) if parts else None,
            document_count=len(parts),
        )

    # ------------------------------------------------------------------ helpers

    def _document_tokens(self, attachment_id: str) -> int:
        content = self.attachment_service.get_attachment_content(attachment_id)
        return estimate_tokens(content) if content else 0

    def _delete_file_if_unused(self, attachment_id: str):
        if not self.repository.is_document_in_use(attachment_id):
            self.attachment_service.repository.delete(attachment_id)

    @staticmethod
    def _clean_name(name: str) -> str:
        name = (name or "").strip()
        if not name:
            raise ValueError("Project name is required")
        if len(name) > 100:
            raise ValueError("Project name must be 100 characters or fewer")
        return name


# Singleton instance
_project_service: ProjectService | None = None


def get_project_service() -> ProjectService:
    """Get project service singleton."""
    global _project_service
    if _project_service is None:
        _project_service = ProjectService()
    return _project_service
