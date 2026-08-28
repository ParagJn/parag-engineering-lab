"""Sessions router."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..models import Session
from ..repositories import SessionRepository
from ..services import get_session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionResponse(BaseModel):
    """Session response model."""
    session_id: str
    created_at: str
    updated_at: str
    title: str


class SessionListItem(BaseModel):
    """Session list item."""
    session_id: str
    title: str
    created_at: str
    updated_at: str


class UpdateSessionRequest(BaseModel):
    """Update session request."""
    title: str


@router.post("", response_model=SessionResponse)
async def create_session():
    """Create a new session."""
    session_service = get_session_service()
    session = session_service.create_session()
    
    return SessionResponse(
        session_id=session.session_id,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        title=session.title,
    )


@router.get("", response_model=list[SessionListItem])
async def list_sessions():
    """List all sessions."""
    session_service = get_session_service()
    sessions = session_service.list_sessions()
    
    return [
        SessionListItem(
            session_id=s.session_id,
            title=s.title,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
        )
        for s in sessions
    ]


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get a session by ID."""
    session_service = get_session_service()
    session = session_service.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Convert to JSON-serializable format
    return session.model_dump(mode="json")


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    session_service = get_session_service()
    deleted = session_service.delete_session(session_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"status": "deleted"}


@router.patch("/{session_id}")
async def update_session(session_id: str, request: UpdateSessionRequest):
    """Update a session (rename)."""
    session_service = get_session_service()
    repository = SessionRepository()
    
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Update title
    session.title = request.title
    repository.update(session)
    
    return {"status": "updated"}
