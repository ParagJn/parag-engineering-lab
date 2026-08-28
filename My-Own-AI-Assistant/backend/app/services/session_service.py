"""Session service for business logic."""

import uuid
from datetime import datetime
from typing import Optional

from ..models import Session
from ..repositories import SessionRepository


class SessionService:
    """Service for session management."""
    
    def __init__(self, repository: Optional[SessionRepository] = None):
        """Initialize session service."""
        self.repository = repository or SessionRepository()
    
    def create_session(self) -> Session:
        """Create a new session."""
        session_id = self._generate_session_id()
        
        session = Session(
            session_id=session_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            title="New conversation",
            messages=[],
            attachment_ids=[],
        )
        
        return self.repository.create(session)
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self.repository.get(session_id)
    
    def list_sessions(self) -> list[Session]:
        """List all sessions."""
        return self.repository.list_all()
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        return self.repository.delete(session_id)
    
    def update_session_title(self, session: Session, first_message: str):
        """Update session title from first message."""
        if first_message:
            # Use first 50 characters as title
            title = first_message[:50].strip()
            if len(first_message) > 50:
                title += "..."
            session.title = title
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return f"sess_{uuid.uuid4().hex[:16]}"


# Singleton instance
_session_service: SessionService | None = None


def get_session_service() -> SessionService:
    """Get session service singleton."""
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service
