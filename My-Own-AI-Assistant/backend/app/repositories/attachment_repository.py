"""Attachment repository for file storage."""

import json
from pathlib import Path
from typing import Optional

from ..config import config
from ..models import Attachment


class AttachmentRepository:
    """Repository for attachment persistence."""
    
    def __init__(self, documents_dir: Optional[Path] = None):
        """Initialize repository."""
        self.documents_dir = documents_dir or config.DOCUMENTS_DIR
        self.documents_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_attachment_dir(self, attachment_id: str) -> Path:
        """Get directory for attachment."""
        return self.documents_dir / attachment_id
    
    def _get_metadata_path(self, attachment_id: str) -> Path:
        """Get path to attachment metadata file."""
        return self._get_attachment_dir(attachment_id) / "metadata.json"
    
    def create(self, attachment: Attachment) -> Attachment:
        """Create a new attachment."""
        attachment_dir = self._get_attachment_dir(attachment.attachment_id)
        attachment_dir.mkdir(parents=True, exist_ok=True)
        
        metadata_path = self._get_metadata_path(attachment.attachment_id)
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(
                attachment.model_dump(mode="json"),
                f,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        
        return attachment
    
    def get(self, attachment_id: str) -> Optional[Attachment]:
        """Get attachment by ID."""
        metadata_path = self._get_metadata_path(attachment_id)
        
        if not metadata_path.exists():
            return None
        
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Attachment(**data)
        except Exception as e:
            raise RuntimeError(f"Failed to load attachment {attachment_id}: {e}") from e
    
    def update(self, attachment: Attachment) -> Attachment:
        """Update attachment metadata."""
        metadata_path = self._get_metadata_path(attachment.attachment_id)
        
        if not metadata_path.exists():
            raise ValueError(f"Attachment {attachment.attachment_id} does not exist")
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(
                attachment.model_dump(mode="json"),
                f,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        
        return attachment
    
    def delete(self, attachment_id: str) -> bool:
        """Delete an attachment and its files."""
        attachment_dir = self._get_attachment_dir(attachment_id)
        
        if not attachment_dir.exists():
            return False
        
        # Delete all files in the directory
        for file in attachment_dir.iterdir():
            file.unlink()
        
        # Delete the directory
        attachment_dir.rmdir()
        return True
    
    def get_file_path(self, attachment_id: str, filename: str) -> Path:
        """Get path to store a file."""
        return self._get_attachment_dir(attachment_id) / filename
    
    def get_content_markdown_path(self, attachment_id: str) -> Path:
        """Get path for content markdown."""
        return self._get_attachment_dir(attachment_id) / "content.md"
