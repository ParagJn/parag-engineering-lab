"""Model service for IBM ICA integration."""

from typing import Any

from ..config import config
from ..ibm_ica_client import IBMICAClient, IBMICAError
from ..models import Message, MessageRole


class ModelService:
    """Service for interacting with the AI model."""
    
    def __init__(self):
        """Initialize model service."""
        # Validate configuration
        config.validate()
        
        # Initialize IBM ICA client
        self.client = IBMICAClient(
            endpoint=config.IBM_ICA_ENDPOINT,
            api_key=config.IBM_ICA_API_KEY,
            model_id=config.IBM_ICA_MODEL_ID,
            timeout=config.MODEL_TIMEOUT,
            insecure_tls=config.IBM_ICA_INSECURE_TLS,
        )
    
    async def generate(
        self,
        messages: list[Message],
        attachments_context: str | None = None,
        max_tokens: int | None = None,
        model: str = "claude",
        images: list[dict] | None = None,
    ) -> dict[str, Any]:
        """
        Generate a response from the model.

        Args:
            messages: List of conversation messages
            attachments_context: Optional context from attachments
            max_tokens: Maximum tokens to generate
            model: Model provider choice ("claude" or "gemini")
            images: Optional list of {filename, mime_type, data (base64)} dicts to attach
                to the current turn for vision analysis

        Returns:
            Dictionary with response text and usage information
        """
        # Build message list for the model
        model_messages = self._build_model_messages(messages, attachments_context, images)
        model_id = config.MODEL_CHOICES.get(model, config.IBM_ICA_MODEL_ID)

        # Call the model
        try:
            result = self.client.chat(
                messages=model_messages,
                max_tokens=max_tokens or config.MAX_TOKENS,
                model_id=model_id,
            )
            
            return {
                "text": result["text"],
                "prompt_tokens": result["prompt_tokens"],
                "completion_tokens": result["completion_tokens"],
                "total_tokens": result["total_tokens"],
                "estimated": result["estimated"],
            }
        except IBMICAError as e:
            raise RuntimeError(f"Model generation failed: {str(e)}") from e
    
    def _build_model_messages(
        self,
        messages: list[Message],
        attachments_context: str | None = None,
        images: list[dict] | None = None,
    ) -> list[dict]:
        """Build message list for the model."""
        model_messages = []

        # Add system message
        system_content = "You are a helpful AI assistant. You help users with technical questions, code, and document analysis."

        if attachments_context:
            system_content += f"\n\n{attachments_context}"

        model_messages.append({
            "role": "system",
            "content": system_content,
        })

        # Add conversation history
        for msg in messages:
            # Skip system messages as we've already added one
            if msg.role == MessageRole.SYSTEM or msg.role == "system":
                continue

            # Handle both enum and string role values
            role_value = msg.role.value if hasattr(msg.role, 'value') else msg.role

            model_messages.append({
                "role": role_value,
                "content": msg.content,
            })

        # Attach embedded images (vision analysis) to the current user turn.
        # Skip non-web image formats (e.g. EMF/WMF/TIFF from Office docs) that
        # vision models generally can't decode.
        supported_images = [
            img for img in (images or [])
            if img.get("mime_type") in ("image/png", "image/jpeg", "image/gif", "image/webp")
        ]
        if supported_images and model_messages and model_messages[-1]["role"] == "user":
            last_message = model_messages[-1]
            content_blocks: list[dict] = [{"type": "text", "text": last_message["content"]}]
            for image in supported_images:
                content_blocks.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image['mime_type']};base64,{image['data']}",
                    },
                })
            last_message["content"] = content_blocks

        return model_messages


# Singleton instance
_model_service: ModelService | None = None


def get_model_service() -> ModelService:
    """Get model service singleton."""
    global _model_service
    if _model_service is None:
        _model_service = ModelService()
    return _model_service
