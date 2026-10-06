"""Projects router."""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..config import config
from ..models import Project
from ..services import (
    ModelRateLimitError,
    ProjectBudgetError,
    get_attachment_service,
    get_project_service,
)
from ..services.project_service import ProjectDocument

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectSummary(BaseModel):
    """Project list item."""
    project_id: str
    name: str
    description: str
    instructions: str
    created_at: str
    updated_at: str
    session_count: int
    document_count: int
    context_tokens: int


class ProjectDocumentResponse(BaseModel):
    """A document pinned to a project."""
    attachment_id: str
    filename: str
    mime_type: str
    size_bytes: int
    status: str
    tokens: int
    created_at: str


class ProjectDetail(ProjectSummary):
    """Project with its documents and budget."""
    documents: list[ProjectDocumentResponse]
    context_budget_tokens: int


class CreateProjectRequest(BaseModel):
    """Create project request."""
    name: str
    description: str = ""
    instructions: str = ""


class UpdateProjectRequest(BaseModel):
    """Update project request."""
    name: str | None = None
    description: str | None = None
    instructions: str | None = None


def _document_response(document: ProjectDocument) -> ProjectDocumentResponse:
    a = document.attachment
    return ProjectDocumentResponse(
        attachment_id=a.attachment_id,
        filename=a.filename,
        mime_type=a.mime_type,
        size_bytes=a.size_bytes,
        status=getattr(a.status, "value", a.status),
        tokens=document.tokens,
        created_at=a.created_at.isoformat(),
    )


def _summary_fields(project: Project, session_count: int, documents: list[ProjectDocument]) -> dict:
    return {
        "project_id": project.project_id,
        "name": project.name,
        "description": project.description,
        "instructions": project.instructions,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
        "session_count": session_count,
        "document_count": len(documents),
        "context_tokens": sum(d.tokens for d in documents),
    }


def _detail(project: Project) -> ProjectDetail:
    service = get_project_service()
    documents = service.list_documents(project.project_id)
    session_count = service.repository.session_counts().get(project.project_id, 0)
    return ProjectDetail(
        **_summary_fields(project, session_count, documents),
        documents=[_document_response(d) for d in documents],
        context_budget_tokens=config.PROJECT_CONTEXT_MAX_TOKENS,
    )


def _get_project_or_404(project_id: str) -> Project:
    project = get_project_service().get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("", response_model=list[ProjectSummary])
async def list_projects():
    """List all projects."""
    service = get_project_service()
    counts = service.repository.session_counts()
    return [
        ProjectSummary(**_summary_fields(p, counts.get(p.project_id, 0), service.list_documents(p.project_id)))
        for p in service.list_projects()
    ]


@router.post("", response_model=ProjectDetail)
async def create_project(request: CreateProjectRequest):
    """Create a project."""
    try:
        project = get_project_service().create_project(
            request.name, request.description, request.instructions
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _detail(project)


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(project_id: str):
    """Get a project with its documents."""
    return _detail(_get_project_or_404(project_id))


@router.patch("/{project_id}", response_model=ProjectDetail)
async def update_project(project_id: str, request: UpdateProjectRequest):
    """Rename a project or change its description/instructions."""
    project = _get_project_or_404(project_id)
    try:
        project = get_project_service().update_project(
            project, request.name, request.description, request.instructions
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _detail(project)


@router.delete("/{project_id}")
async def delete_project(project_id: str, delete_chats: bool = False):
    """Delete a project. Its chats are kept (moved out of the project) unless delete_chats=true."""
    if not get_project_service().delete_project(project_id, delete_chats=delete_chats):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted"}


@router.post("/{project_id}/documents", response_model=ProjectDocumentResponse)
async def upload_project_document(project_id: str, file: UploadFile = File(...)):
    """Upload a file and pin it to the project."""
    _get_project_or_404(project_id)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    attachment_service = get_attachment_service()
    content = await file.read()
    await file.seek(0)

    try:
        attachment = await attachment_service.create_attachment(
            file=file.file,
            filename=file.filename,
            size_bytes=len(content),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ModelRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Too many requests while reading the file. Please wait and try again.",
        )
    except Exception as e:
        logger.exception("Failed to upload project document for %s", project_id)
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

    try:
        document = get_project_service().pin_document(project_id, attachment.attachment_id)
    except Exception as e:
        # The file was uploaded only for this project, so don't keep it if it can't be pinned
        attachment_service.repository.delete(attachment.attachment_id)
        if isinstance(e, (ProjectBudgetError, ValueError)):
            raise HTTPException(status_code=400, detail=str(e))
        logger.exception("Failed to pin project document for %s", project_id)
        raise HTTPException(status_code=500, detail=f"Failed to add file: {str(e)}")

    return _document_response(document)


@router.post("/{project_id}/documents/{attachment_id}", response_model=ProjectDocumentResponse)
async def pin_existing_document(project_id: str, attachment_id: str):
    """Pin a file that was already uploaded (e.g. in a chat) to the project."""
    _get_project_or_404(project_id)
    try:
        document = get_project_service().pin_document(project_id, attachment_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _document_response(document)


@router.delete("/{project_id}/documents/{attachment_id}")
async def unpin_document(project_id: str, attachment_id: str):
    """Remove a file from the project (the file itself is deleted if nothing else uses it)."""
    _get_project_or_404(project_id)
    if not get_project_service().unpin_document(project_id, attachment_id):
        raise HTTPException(status_code=404, detail="File is not in this project")
    return {"status": "removed"}
