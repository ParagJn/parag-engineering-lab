"""Attachment service for file management."""

import mimetypes
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO, Optional

from ..config import config
from ..models import Attachment, AttachmentStatus
from ..repositories import AttachmentRepository
from .extraction_service import get_extraction_service


class AttachmentService:
    """Service for attachment management."""
    
    def __init__(
        self,
        repository: Optional[AttachmentRepository] = None,
    ):
        """Initialize attachment service."""
        self.repository = repository or AttachmentRepository()
        self.extraction_service = get_extraction_service()
    
    async def create_attachment(
        self,
        file: BinaryIO,
        filename: str,
        size_bytes: int,
    ) -> Attachment:
        """
        Create a new attachment from uploaded file.
        
        Args:
            file: File object
            filename: Original filename
            size_bytes: File size in bytes
            
        Returns:
            Created attachment
        """
        # Generate attachment ID
        attachment_id = self._generate_attachment_id()
        
        # Detect MIME type
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        
        # Validate file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in config.ALLOWED_EXTENSIONS:
            raise ValueError(f"File type {file_ext} is not allowed")
        
        # Validate file size
        if size_bytes > config.MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds maximum allowed size")
        
        # Get storage paths
        stored_path = self.repository.get_file_path(attachment_id, filename)
        
        # Save file
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        with open(stored_path, "wb") as f:
            shutil.copyfileobj(file, f)
        
        # Create attachment record
        attachment = Attachment(
            attachment_id=attachment_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            stored_path=str(stored_path),
            content_markdown_path=None,
            status=AttachmentStatus.UPLOADED,
        )
        
        # Save metadata
        self.repository.create(attachment)
        
        # Process attachment asynchronously
        await self._process_attachment(attachment)
        
        return attachment
    
    async def _process_attachment(self, attachment: Attachment):
        """Process attachment to extract content."""
        try:
            # Update status
            attachment.status = AttachmentStatus.PROCESSING
            self.repository.update(attachment)
            
            # Extract content
            file_path = Path(attachment.stored_path)
            markdown_content = self.extraction_service.extract_to_markdown(
                file_path,
                attachment.mime_type,
            )
            
            # Save markdown
            markdown_path = self.repository.get_content_markdown_path(attachment.attachment_id)
            with open(markdown_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            
            # Update attachment
            attachment.content_markdown_path = str(markdown_path)
            attachment.status = AttachmentStatus.READY
            self.repository.update(attachment)
            
        except Exception as e:
            # Mark as failed
            attachment.status = AttachmentStatus.FAILED
            self.repository.update(attachment)
            raise RuntimeError(f"Failed to process attachment: {str(e)}") from e
    
    def get_attachment(self, attachment_id: str) -> Optional[Attachment]:
        """Get attachment by ID."""
        return self.repository.get(attachment_id)
    
    def get_attachment_content(self, attachment_id: str) -> str | None:
        """Get extracted markdown content for attachment."""
        attachment = self.repository.get(attachment_id)
        
        if not attachment or not attachment.content_markdown_path:
            return None
        
        markdown_path = Path(attachment.content_markdown_path)
        if not markdown_path.exists():
            return None
        
        with open(markdown_path, "r", encoding="utf-8") as f:
            return f.read()
    
    def _generate_attachment_id(self) -> str:
        """Generate a unique attachment ID."""
        return f"att_{uuid.uuid4().hex[:16]}"


# Singleton instance
_attachment_service: AttachmentService | None = None


def get_attachment_service() -> AttachmentService:
    """Get attachment service singleton."""
    global _attachment_service
    if _attachment_service is None:
        _attachment_service = AttachmentService()
    return _attachment_service
