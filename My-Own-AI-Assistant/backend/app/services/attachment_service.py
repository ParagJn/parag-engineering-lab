"""Attachment service for file management."""

import asyncio
import base64
import mimetypes
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO, Optional

from ..config import config
from ..models import Attachment, AttachmentImage, AttachmentStatus
from ..repositories import AttachmentRepository
from .extraction_service import get_extraction_service
from .image_understanding_service import get_image_understanding_service
from .model_service import ModelRateLimitError

# Scanned PDFs: cap pages read (each is one vision call) and how many run at once
SCANNED_PDF_MAX_PAGES = 30
SCANNED_PDF_CONCURRENCY = 4


class AttachmentService:
    """Service for attachment management."""
    
    def __init__(
        self,
        repository: Optional[AttachmentRepository] = None,
    ):
        """Initialize attachment service."""
        self.repository = repository or AttachmentRepository()
        self.extraction_service = get_extraction_service()
        self.image_understanding_service = get_image_understanding_service()
    
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
            max_mb = config.MAX_FILE_SIZE / (1024 * 1024)
            raise ValueError(f"File size exceeds the maximum allowed size of {max_mb:.0f}MB")
        
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
            
            file_path = Path(attachment.stored_path)

            # Images: Claude converts them to Markdown. The image itself is not
            # passed on, so the selected model works from that Markdown.
            if file_path.suffix.lower() in config.IMAGE_EXTENSIONS:
                markdown_content = await self.image_understanding_service.image_to_markdown(
                    file_path, attachment.mime_type, attachment.filename
                )
                self._save_markdown(attachment, markdown_content)
                attachment.status = AttachmentStatus.READY
                self.repository.update(attachment)
                return

            # Scanned / image-only PDFs have no text layer: render each page and
            # let Claude read it, the same way pasted images are handled.
            if file_path.suffix.lower() == ".pdf" and not self.extraction_service.pdf_has_text(file_path):
                markdown_content = await self._scanned_pdf_to_markdown(file_path, attachment)
                self._save_markdown(attachment, markdown_content)
                attachment.status = AttachmentStatus.READY
                self.repository.update(attachment)
                return

            # Extract embedded images first, so the markdown can note how many were found
            extracted_images = self.extraction_service.extract_images(
                file_path,
                attachment.mime_type,
            )

            images: list[AttachmentImage] = []
            for image in extracted_images:
                image_path = self.repository.get_image_path(attachment.attachment_id, image.filename)
                image_path.parent.mkdir(parents=True, exist_ok=True)
                with open(image_path, "wb") as f:
                    f.write(image.data)
                images.append(
                    AttachmentImage(
                        filename=image.filename,
                        mime_type=image.mime_type,
                        stored_path=str(image_path),
                    )
                )

            # Extract text content
            markdown_content = self.extraction_service.extract_to_markdown(
                file_path,
                attachment.mime_type,
                image_count=len(images),
            )

            self._save_markdown(attachment, markdown_content)
            attachment.images = images
            attachment.status = AttachmentStatus.READY
            self.repository.update(attachment)
            
        except ModelRateLimitError:
            attachment.status = AttachmentStatus.FAILED
            self.repository.update(attachment)
            raise
        except Exception as e:
            # Mark as failed
            attachment.status = AttachmentStatus.FAILED
            self.repository.update(attachment)
            raise RuntimeError(f"Failed to process attachment: {str(e)}") from e

    async def _scanned_pdf_to_markdown(self, file_path: Path, attachment: Attachment) -> str:
        """Read a scanned PDF page by page with the image-reading model."""
        pages, total_pages = await asyncio.to_thread(
            self.extraction_service.render_pdf_pages, file_path, SCANNED_PDF_MAX_PAGES
        )
        semaphore = asyncio.Semaphore(SCANNED_PDF_CONCURRENCY)

        async def read_page(page_num: int, png: bytes) -> str:
            async with semaphore:
                return await self.image_understanding_service.describe_image(
                    png,
                    "image/png",
                    context=(
                        f"This is page {page_num} of {total_pages} of a scanned PDF document "
                        f"named \"{attachment.filename}\"."
                    ),
                )

        page_texts = await asyncio.gather(
            *(read_page(num, png) for num, png in enumerate(pages, 1))
        )

        markdown = f"# {attachment.filename}\n\n"
        markdown += f"**Type:** {attachment.mime_type} (scanned, {total_pages} page(s))\n\n"
        markdown += (
            "_This PDF has no text layer (scanned or image-only). Each page was read by an "
            "image-reading model, so you are seeing its transcription, which may contain "
            "reading errors._\n\n"
        )
        if total_pages > len(pages):
            markdown += (
                f"_Only the first {len(pages)} of {total_pages} pages were read; the rest of "
                "the document is not included below._\n\n"
            )
        markdown += "---\n\n"
        markdown += "\n\n".join(
            f"## Page {num}\n\n{text.strip()}" for num, text in enumerate(page_texts, 1)
        )
        return markdown

    def _save_markdown(self, attachment: Attachment, markdown_content: str):
        """Write extracted markdown and point the attachment at it."""
        markdown_path = self.repository.get_content_markdown_path(attachment.attachment_id)
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        attachment.content_markdown_path = str(markdown_path)
    
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
    
    def get_attachment_images(self, attachment_id: str) -> list[dict]:
        """Get base64-encoded image data for an attachment, for vision analysis."""
        attachment = self.repository.get(attachment_id)
        if not attachment or not attachment.images:
            return []

        images = []
        for image in attachment.images:
            image_path = Path(image.stored_path)
            if not image_path.exists():
                continue
            with open(image_path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            images.append({
                "filename": image.filename,
                "mime_type": image.mime_type,
                "data": data,
            })
        return images

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
