"""Image processing using Azure OpenAI vision capabilities."""
import logging
from typing import List, Optional

from .azure_openai_client import get_azure_client

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Processor for extracting information from images using Azure OpenAI."""

    def __init__(self):
        """Initialize the image processor."""
        self.client = get_azure_client()

    def generate_caption(self, image_base64: str, content_type: str) -> Optional[str]:
        """
        Generate a concise caption for an image.
        
        Args:
            image_base64: Base64-encoded image data
            content_type: MIME type of the image
            
        Returns:
            Caption text or None if failed
        """
        if not self.client.is_enabled():
            logger.info("AI enrichment disabled - skipping caption generation")
            return None

        logger.info(f"Generating caption for image ({content_type})...")

        messages = [
            {
                "role": "system",
                "content": "You generate concise, factual captions for business documents."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Write a one-sentence caption describing the image for search and retrieval.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{content_type};base64,{image_base64}",
                        },
                    },
                ],
            },
        ]

        result = self.client.call_chat_completion(messages, max_tokens=4000)
        
        if result:
            logger.info(f"✓ Caption generated: {result}")
        else:
            logger.error("✗ Caption generation failed - check Azure OpenAI configuration and API status")
            
        return result

    def extract_as_markdown(self, image_base64: str, content_type: str) -> Optional[str]:
        """
        Extract image content as markdown format.
        
        Handles:
        - Text extraction (OCR)
        - Tables → markdown tables
        - Charts/diagrams → detailed descriptions
        - Flowcharts → flow descriptions
        
        Args:
            image_base64: Base64-encoded image data
            content_type: MIME type of the image
            
        Returns:
            Markdown representation of image content or None if failed
        """
        if not self.client.is_enabled():
            logger.info("AI enrichment disabled - skipping markdown extraction")
            return None

        logger.info(f"Extracting markdown from image ({content_type})...")

        messages = [
            {
                "role": "system",
                "content": "You are an expert at extracting content from images and converting it to markdown format."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Analyze this image and extract all content as markdown. "
                            "If it contains text, transcribe it exactly. "
                            "If it contains a table, convert it to markdown table format. "
                            "If it contains a chart or diagram, describe it in detail with structured markdown. "
                            "If it contains a flowchart, describe the flow with proper hierarchy. "
                            "Preserve formatting and structure as much as possible in markdown."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{content_type};base64,{image_base64}",
                        },
                    },
                ],
            },
        ]

        result = self.client.call_chat_completion(messages, max_tokens=4000)
        
        if result:
            preview = result[:200] + "..." if len(result) > 200 else result
            logger.info(f"✓ Markdown extracted ({len(result)} chars): {preview}")
        else:
            logger.error("✗ Markdown extraction failed - check Azure OpenAI configuration and API status")
            
        return result


class TableProcessor:
    """Processor for generating table summaries using Azure OpenAI."""

    def __init__(self):
        """Initialize the table processor."""
        self.client = get_azure_client()

    def generate_summary(self, table_markdown: str, rows: List[List[str]]) -> Optional[str]:
        """
        Generate a semantic summary of a table for search.
        
        Args:
            table_markdown: Markdown representation of the table
            rows: Raw table data as list of lists
            
        Returns:
            Summary text or None if failed
        """
        if not self.client.is_enabled():
            logger.info("AI enrichment disabled - skipping table summary")
            return None

        logger.info(f"Generating summary for table ({len(rows)} rows)...")

        messages = [
            {
                "role": "system",
                "content": "You summarize tables into short searchable text."
            },
            {
                "role": "user",
                "content": (
                    "Summarize this table in 1-2 sentences for semantic search. "
                    "Focus on the key entities and measures.\n\n"
                    f"{table_markdown}"
                ),
            },
        ]

        result = self.client.call_chat_completion(messages, max_tokens=120)
        
        if result:
            logger.info(f"✓ Table summary: {result}")
        else:
            logger.error("✗ Table summary generation failed - check Azure OpenAI configuration and API status")
            
        return result


# Global singleton instances
_image_processor = None
_table_processor = None


def get_image_processor() -> ImageProcessor:
    """Get or create the global image processor instance."""
    global _image_processor
    if _image_processor is None:
        _image_processor = ImageProcessor()
    return _image_processor


def get_table_processor() -> TableProcessor:
    """Get or create the global table processor instance."""
    global _table_processor
    if _table_processor is None:
        _table_processor = TableProcessor()
    return _table_processor
