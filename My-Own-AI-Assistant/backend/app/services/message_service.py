"""Message service for business logic."""

import uuid
from datetime import datetime

from ..models import Message, MessageAttachment, MessageRole, Session
from ..repositories import SessionRepository


class MessageService:
    """Service for message management."""
    
    def __init__(self, repository: SessionRepository | None = None):
        """Initialize message service."""
        self.repository = repository or SessionRepository()
    
    def add_user_message(
        self,
        session: Session,
        content: str,
        attachment_ids: list[str] | None = None,
    ) -> Message:
        """Add a user message to the session."""
        message = Message(
            id=self._generate_message_id(),
            role=MessageRole.USER,
            content=content,
            created_at=datetime.utcnow(),
            attachments=[],
        )
        
        session.messages.append(message)
        return message
    
    def add_assistant_message(
        self,
        session: Session,
        content: str,
    ) -> Message:
        """Add an assistant message to the session."""
        message = Message(
            id=self._generate_message_id(),
            role=MessageRole.ASSISTANT,
            content=content,
            created_at=datetime.utcnow(),
            attachments=[],
        )
        
        session.messages.append(message)
        return message
    
    def _generate_message_id(self) -> str:
        """Generate a unique message ID."""
        return f"msg_{uuid.uuid4().hex[:16]}"


# Singleton instance
_message_service: MessageService | None = None


def get_message_service() -> MessageService:
    """Get message service singleton."""
    global _message_service
    if _message_service is None:
        _message_service = MessageService()
    return _message_service
