"""Document extraction service."""

import mimetypes
from pathlib import Path
from typing import Protocol


_markitdown = None


def _markitdown_convert(path: Path) -> str | None:
    """
    Convert a document to Markdown with MarkItDown (keeps headings, lists and
    tables far better than raw text extraction). Returns None if MarkItDown is
    unavailable, fails, or produces no text, so callers can fall back.
    """
    global _markitdown
    try:
        if _markitdown is None:
            from markitdown import MarkItDown

            _markitdown = MarkItDown(enable_plugins=False)
        text = _markitdown.convert(str(path)).text_content or ""
    except Exception:
        return None
    return text if text.strip() else None


class ExtractedImage:
    """An image extracted from a document."""

    def __init__(self, data: bytes, mime_type: str, filename: str):
        self.data = data
        self.mime_type = mime_type
        self.filename = filename


class DocumentExtractor(Protocol):
    """Protocol for document extractors."""

    def supports(self, mime_type: str, filename: str) -> bool:
        """Check if extractor supports this file type."""
        ...

    def extract(self, path: Path) -> str:
        """Extract text content from file."""
        ...

    def extract_images(self, path: Path) -> list[ExtractedImage]:
        """Extract embedded images from file. Default: none."""
        return []


class TextExtractor:
    """Extractor for plain text files."""
    
    def supports(self, mime_type: str, filename: str) -> bool:
        """Check if file is plain text."""
        return mime_type.startswith("text/") or filename.lower().endswith((".txt", ".md", ".markdown"))
    
    def extract(self, path: Path) -> str:
        """Extract text content."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return content
        except UnicodeDecodeError:
            # Try with latin-1 encoding
            with open(path, "r", encoding="latin-1") as f:
                content = f.read()
            return content


class PDFExtractor:
    """Extractor for PDF files."""
    
    def supports(self, mime_type: str, filename: str) -> bool:
        """Check if file is PDF."""
        return mime_type == "application/pdf" or filename.lower().endswith(".pdf")
    
    def extract(self, path: Path) -> str:
        """Extract text from PDF: MarkItDown first, PyPDF2 as fallback."""
        markdown = _markitdown_convert(path)
        if markdown:
            # pdfminer separates pages with form feeds; keep page headings so the
            # model can point to where something came from
            pages = [page.strip() for page in markdown.split("\f")]
            if len(pages) > 1:
                return "\n\n".join(
                    f"## Page {num}\n\n{text}" for num, text in enumerate(pages, 1) if text
                )
            return markdown.strip()

        try:
            import PyPDF2
            
            text_parts = []
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page_num, page in enumerate(reader.pages, 1):
                    text = page.extract_text()
                    if text.strip():
                        text_parts.append(f"## Page {page_num}\n\n{text.strip()}")
            
            return "\n\n".join(text_parts) if text_parts else "No text content extracted from PDF."
        except ImportError:
            return "PDF extraction requires PyPDF2. Install with: pip install PyPDF2"
        except Exception as e:
            return f"Error extracting PDF: {str(e)}"

    def extract_images(self, path: Path) -> list[ExtractedImage]:
        """Extract embedded images from PDF pages."""
        images: list[ExtractedImage] = []
        try:
            import PyPDF2

            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page_num, page in enumerate(reader.pages, 1):
                    page_images = getattr(page, "images", [])
                    for img_num, image in enumerate(page_images, 1):
                        mime_type = mimetypes.guess_type(image.name)[0] or "image/png"
                        filename = f"page{page_num}_image{img_num}_{image.name}"
                        images.append(ExtractedImage(image.data, mime_type, filename))
        except Exception:
            # If image extraction fails, just skip images rather than failing the whole upload.
            return images

        return images


class DocxExtractor:
    """Extractor for DOCX files."""
    
    def supports(self, mime_type: str, filename: str) -> bool:
        """Check if file is DOCX."""
        return (
            mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or filename.lower().endswith(".docx")
        )
    
    def extract(self, path: Path) -> str:
        """Extract text from DOCX: MarkItDown first (keeps tables), python-docx as fallback."""
        markdown = _markitdown_convert(path)
        if markdown:
            return markdown.strip()

        try:
            import docx
            
            doc = docx.Document(path)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            return "\n\n".join(paragraphs) if paragraphs else "No text content extracted from DOCX."
        except ImportError:
            return "DOCX extraction requires python-docx. Install with: pip install python-docx"
        except Exception as e:
            return f"Error extracting DOCX: {str(e)}"

    def extract_images(self, path: Path) -> list[ExtractedImage]:
        """Extract embedded images from a DOCX file's relationships."""
        images: list[ExtractedImage] = []
        try:
            import docx

            doc = docx.Document(path)
            img_num = 0
            for rel in doc.part.rels.values():
                if "image" not in rel.reltype:
                    continue
                img_num += 1
                image_part = rel.target_part
                mime_type = image_part.content_type or "image/png"
                ext = mimetypes.guess_extension(mime_type) or ".png"
                filename = f"image{img_num}{ext}"
                images.append(ExtractedImage(image_part.blob, mime_type, filename))
        except Exception:
            return images

        return images


class ExtractionService:
    """Service for extracting content from various file types."""
    
    def __init__(self):
        """Initialize extraction service."""
        self.extractors: list[DocumentExtractor] = [
            TextExtractor(),
            PDFExtractor(),
            DocxExtractor(),
        ]
    
    def extract_to_markdown(self, file_path: Path, mime_type: str, image_count: int = 0) -> str:
        """
        Extract content from a file and convert to Markdown.

        Args:
            file_path: Path to the file
            mime_type: MIME type of the file
            image_count: Number of embedded images found (for a note in the markdown)

        Returns:
            Markdown-formatted content
        """
        filename = file_path.name

        # Find appropriate extractor
        for extractor in self.extractors:
            if extractor.supports(mime_type, filename):
                content = extractor.extract(file_path)

                # Wrap in Markdown structure
                markdown = f"# {filename}\n\n"
                markdown += f"**Type:** {mime_type}\n\n"
                markdown += "---\n\n"
                markdown += content

                if image_count:
                    markdown += (
                        f"\n\n---\n\n## Embedded Images\n\n"
                        f"This document contains {image_count} embedded image(s), attached "
                        f"separately below for visual analysis."
                    )

                return markdown

        # No extractor found
        return f"# {filename}\n\n**Type:** {mime_type}\n\nNo extractor available for this file type."

    @staticmethod
    def pdf_has_text(file_path: Path) -> bool:
        """True if any page of the PDF has a text layer (False for scanned / image-only PDFs)."""
        try:
            import pypdfium2 as pdfium

            pdf = pdfium.PdfDocument(str(file_path))
            try:
                for page in pdf:
                    if page.get_textpage().get_text_range().strip():
                        return True
            finally:
                pdf.close()
        except Exception:
            # Can't tell; assume text so the normal extraction path runs
            return True
        return False

    @staticmethod
    def render_pdf_pages(file_path: Path, max_pages: int, scale: float = 2.0) -> tuple[list[bytes], int]:
        """Render the first `max_pages` pages as PNG bytes. Returns (pngs, total page count)."""
        import io

        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(file_path))
        try:
            total = len(pdf)
            pngs: list[bytes] = []
            for index in range(min(total, max_pages)):
                image = pdf[index].render(scale=scale).to_pil()
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                pngs.append(buffer.getvalue())
            return pngs, total
        finally:
            pdf.close()

    def extract_images(self, file_path: Path, mime_type: str) -> list[ExtractedImage]:
        """Extract embedded images from a file, if the matching extractor supports it."""
        filename = file_path.name
        for extractor in self.extractors:
            if extractor.supports(mime_type, filename):
                return extractor.extract_images(file_path)
        return []


# Singleton instance
_extraction_service: ExtractionService | None = None


def get_extraction_service() -> ExtractionService:
    """Get extraction service singleton."""
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = ExtractionService()
    return _extraction_service
