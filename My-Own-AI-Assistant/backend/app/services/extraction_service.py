"""Document extraction service."""

import mimetypes
from pathlib import Path
from typing import Protocol


class DocumentExtractor(Protocol):
    """Protocol for document extractors."""
    
    def supports(self, mime_type: str, filename: str) -> bool:
        """Check if extractor supports this file type."""
        ...
    
    def extract(self, path: Path) -> str:
        """Extract text content from file."""
        ...


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
        """Extract text from PDF."""
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


class DocxExtractor:
    """Extractor for DOCX files."""
    
    def supports(self, mime_type: str, filename: str) -> bool:
        """Check if file is DOCX."""
        return (
            mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or filename.lower().endswith(".docx")
        )
    
    def extract(self, path: Path) -> str:
        """Extract text from DOCX."""
        try:
            import docx
            
            doc = docx.Document(path)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            return "\n\n".join(paragraphs) if paragraphs else "No text content extracted from DOCX."
        except ImportError:
            return "DOCX extraction requires python-docx. Install with: pip install python-docx"
        except Exception as e:
            return f"Error extracting DOCX: {str(e)}"


class ExtractionService:
    """Service for extracting content from various file types."""
    
    def __init__(self):
        """Initialize extraction service."""
        self.extractors: list[DocumentExtractor] = [
            TextExtractor(),
            PDFExtractor(),
            DocxExtractor(),
        ]
    
    def extract_to_markdown(self, file_path: Path, mime_type: str) -> str:
        """
        Extract content from a file and convert to Markdown.
        
        Args:
            file_path: Path to the file
            mime_type: MIME type of the file
            
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
                
                return markdown
        
        # No extractor found
        return f"# {filename}\n\n**Type:** {mime_type}\n\nNo extractor available for this file type."


# Singleton instance
_extraction_service: ExtractionService | None = None


def get_extraction_service() -> ExtractionService:
    """Get extraction service singleton."""
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = ExtractionService()
    return _extraction_service
