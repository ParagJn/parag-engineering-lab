"""Session repository for JSON-based persistence."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import config
from ..models import Session


class SessionRepository:
    """Repository for session persistence."""
    
    def __init__(self, sessions_dir: Optional[Path] = None):
        """Initialize repository."""
        self.sessions_dir = sessions_dir or config.SESSIONS_DIR
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_session_path(self, session_id: str) -> Path:
        """Get path to session file."""
        return self.sessions_dir / f"{session_id}.json"
    
    def create(self, session: Session) -> Session:
        """Create a new session."""
        session_path = self._get_session_path(session.session_id)
        
        if session_path.exists():
            raise ValueError(f"Session {session.session_id} already exists")
        
        self._save_atomic(session_path, session)
        return session
    
    def get(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        session_path = self._get_session_path(session_id)
        
        if not session_path.exists():
            return None
        
        try:
            with open(session_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Session(**data)
        except Exception as e:
            raise RuntimeError(f"Failed to load session {session_id}: {e}") from e
    
    def list_all(self) -> list[Session]:
        """List all sessions, ordered by most recently updated."""
        sessions = []
        
        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append(Session(**data))
            except Exception:
                # Skip corrupted files
                continue
        
        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions
    
    def update(self, session: Session) -> Session:
        """Update an existing session."""
        session_path = self._get_session_path(session.session_id)
        
        if not session_path.exists():
            raise ValueError(f"Session {session.session_id} does not exist")
        
        # Update timestamp
        session.updated_at = datetime.utcnow()
        
        self._save_atomic(session_path, session)
        return session
    
    def delete(self, session_id: str) -> bool:
        """Delete a session."""
        session_path = self._get_session_path(session_id)
        
        if not session_path.exists():
            return False
        
        session_path.unlink()
        return True
    
    def _save_atomic(self, path: Path, session: Session):
        """Save session atomically using a temporary file."""
        temp_path = path.with_suffix(".tmp")
        
        try:
            # Write to temporary file
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(
                    session.model_dump(mode="json"),
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str,
                )
            
            # Atomic rename
            temp_path.replace(path)
        except Exception:
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise
