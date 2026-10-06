"""Model service for IBM ICA integration."""

import asyncio
import threading
from typing import Any, AsyncIterator, Iterator

from ..config import config
from ..ibm_ica_client import IBMICAClient, IBMICAError
from ..models import Message, MessageRole
from .web_search_service import get_web_search_service

class ModelRateLimitError(RuntimeError):
    """Raised when the model gateway rate-limits the request (HTTP 429)."""
    pass


# Core rule for every prompt in this app: no answer is better than a wrong one.
ACCURACY_PRINCIPLES = (
    "Accuracy is your top priority. An honest \"I don't know\" is always better than a "
    "confident answer that might be wrong.\n"
    "- Never invent facts, numbers, dates, names, quotes, citations, URLs, file contents, "
    "API names, function signatures, library versions or command options. If you are not "
    "sure something exists or is correct, say so instead of guessing.\n"
    "- If you cannot answer reliably, say plainly that you don't know or can't verify it, "
    "and briefly say what would be needed (a document, more details, web search). A short "
    "honest answer beats a long speculative one.\n"
    "- Keep what you know apart from what you are inferring. Label assumptions, estimates "
    "and opinions as such (for example \"I believe...\", \"likely...\", \"assuming...\").\n"
    "- Don't fill gaps with plausible-sounding detail. If the request is ambiguous or "
    "missing information that changes the answer, ask a clarifying question or state the "
    "assumption you are making.\n"
    "- Your knowledge has a cutoff. For recent events, current prices, latest versions or "
    "anything that changes over time, say your information may be out of date.\n"
    "- For code, only use APIs and options you are confident exist. Mention when code is "
    "untested or depends on a version you are unsure of.\n"
    "- If the user states something incorrect, correct it politely rather than going along "
    "with it.\n"
    "- If you realise part of an earlier answer was wrong, say so and correct it."
)

BASE_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. You help users with technical questions, code, and "
    "document analysis. Be clear, direct and concise, and use Markdown formatting where it "
    "helps readability.\n\n"
    + ACCURACY_PRINCIPLES
)

# How to treat document text, shared by chat attachments and project documents
DOCUMENT_RULES = (
    "- Base your answer on what they actually contain. Quote or closely paraphrase the "
    "relevant part, and name the file it came from when there is more than one.\n"
    "- If the answer isn't in the documents, say so clearly (for example \"The document "
    "doesn't mention this\"). Don't fill the gap by guessing what it probably says.\n"
    "- If you add general knowledge beyond the documents, make it clear that this part "
    "isn't from the document.\n"
    "- Extracted text can be incomplete or garbled (tables, scans, charts). If a relevant "
    "section looks unreadable or missing, say so rather than reconstructing it.\n"
    "- Images reach you as a Markdown description written by an image-reading model, not "
    "the image itself. Treat details marked uncertain or [illegible] as unknown, and don't "
    "claim more certainty than the description gives."
)

ATTACHMENTS_INSTRUCTION = (
    "The user has attached documents and/or images to this message, shown below. When "
    "answering about them:\n" + DOCUMENT_RULES
)

PROJECT_INSTRUCTION = (
    "This chat is part of the user's project \"{name}\". The user wrote these standing "
    "instructions for every chat in the project. Follow them as preferences for tone, format "
    "and focus, but they never override the accuracy rules above: if following them would mean "
    "guessing or stating something you can't support, say so instead."
)

PROJECT_DOCUMENTS_INSTRUCTION = (
    "These reference documents are pinned to the project \"{name}\" and are available in every "
    "chat in it, whether or not the user mentions them. Use them when they are relevant to the "
    "question; you don't need to bring them up otherwise. When answering from them:\n"
    + DOCUMENT_RULES
)


SEARCH_WEB_TOOL = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": (
            "Search the web for up-to-date or external information you don't already know, "
            "such as current events, recent data, or anything outside your training data. "
            "Use this whenever answering the user's request requires current information. "
            "Returns up to 5 DuckDuckGo results, each with title, url and a short snippet "
            "(snippets only, not full page text). On failure it returns an error entry "
            "instead of results; say so rather than guessing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A concise keyword search query; include names, versions or dates when relevant.",
                },
            },
            "required": ["query"],
        },
    },
}


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
        self.web_search_service = get_web_search_service()

    ATTRIBUTION_INSTRUCTION = (
        "Web search is available through the search_web tool. Use it for anything current, "
        "recent or outside what you reliably know, instead of answering from memory.\n"
        "- Search results are short snippets, not full pages. Only state what the snippets "
        "actually support; don't claim to have read a page or pad the answer with detail the "
        "snippets don't contain.\n"
        "- If the results don't answer the question, or the search failed, say so plainly "
        "rather than guessing. If sources disagree, point out the disagreement.\n"
        "- Don't make up URLs or source titles; a list of sources is added to your answer "
        "automatically.\n\n"
        "When your answer draws on information you found via the search_web tool, wrap that "
        "specific sentence, fact, or list/quiz item in an inline HTML tag exactly like this: "
        "<span class=\"web-sourced\">the text here</span>. Every opening tag must have a matching "
        "closing </span>. Do not wrap content that comes from the uploaded document(s) or from "
        "your own general knowledge — leave that as plain text. Only wrap the parts genuinely "
        "sourced from web search results."
    )

    async def generate(
        self,
        messages: list[Message],
        attachments_context: str | None = None,
        max_tokens: int | None = None,
        model: str = "claude",
        images: list[dict] | None = None,
        web_search_enabled: bool = False,
        project_context: dict | None = None,
    ) -> dict[str, Any]:
        """
        Generate a response from the model.

        Args:
            messages: List of conversation messages
            attachments_context: Optional context from attachments
            max_tokens: Maximum tokens to generate
            model: Model provider choice ("claude", "gemini", or "openai")
            images: Optional list of {filename, mime_type, data (base64)} dicts to attach
                to the current turn for vision analysis
            web_search_enabled: Whether to offer the model a "search_web" tool it can
                call to look things up before answering
            project_context: For chats in a project, {"name", "instructions",
                "documents_context"} added to the system prompt

        Returns:
            Dictionary with response text and usage information
        """
        # Build message list for the model
        model_messages = self._build_model_messages(
            messages, attachments_context, images, web_search_enabled, project_context
        )
        model_id = config.MODEL_CHOICES.get(model, config.IBM_ICA_MODEL_ID)
        tools = [SEARCH_WEB_TOOL] if web_search_enabled else None

        # Call the model
        try:
            result = self.client.chat(
                messages=model_messages,
                max_tokens=max_tokens or config.MAX_TOKENS,
                model_id=model_id,
                tools=tools,
            )

            # If the model asked to search the web, run the search(es), feed the
            # results back, and let the model produce its final answer.
            if result.get("tool_calls"):
                result = self._run_tool_calls(
                    model_messages, result, model_id, max_tokens or config.MAX_TOKENS
                )

            return {
                "text": result["text"],
                "prompt_tokens": result["prompt_tokens"],
                "completion_tokens": result["completion_tokens"],
                "total_tokens": result["total_tokens"],
                "estimated": result["estimated"],
            }
        except IBMICAError as e:
            if getattr(e, "http_code", None) == 429:
                raise ModelRateLimitError(str(e)) from e
            raise RuntimeError(f"Model generation failed: {str(e)}") from e

    def _prepare_tool_call_followup(
        self,
        model_messages: list[dict],
        result: dict[str, Any],
    ) -> tuple[list[dict], list[dict]]:
        """Run the requested tool call(s) and build the follow-up message list."""
        tool_calls = result["tool_calls"]
        assistant_message = result.get("raw_assistant_message") or {
            "role": "assistant",
            "content": result["text"],
        }

        follow_up_messages = model_messages + [assistant_message]
        all_results: list[dict] = []

        for call in tool_calls:
            if call.get("name") != "search_web":
                continue
            query = (call.get("arguments") or {}).get("query", "")
            results = self.web_search_service.search(query)
            all_results.extend(results)
            tool_result_text = self.web_search_service.format_results(query, results)

            follow_up_messages.append({
                "role": "tool",
                "tool_call_id": call.get("id"),
                "name": "search_web",
                "content": tool_result_text,
            })

        return follow_up_messages, all_results

    def _run_tool_calls(
        self,
        model_messages: list[dict],
        result: dict[str, Any],
        model_id: str,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Execute requested tool calls and get the model's follow-up answer."""
        follow_up_messages, all_results = self._prepare_tool_call_followup(model_messages, result)

        # The gateway (Bedrock via litellm) requires the `tools` schema to be present
        # on any request whose history includes a tool call/result, even though we
        # just want a plain text answer here.
        final = self.client.chat(
            messages=follow_up_messages,
            max_tokens=max_tokens,
            model_id=model_id,
            tools=[SEARCH_WEB_TOOL],
        )

        sources = self._format_sources(all_results)
        if sources:
            final["text"] = f"{final['text']}\n\n{sources}"

        return final

    async def generate_stream(
        self,
        messages: list[Message],
        attachments_context: str | None = None,
        max_tokens: int | None = None,
        model: str = "claude",
        images: list[dict] | None = None,
        web_search_enabled: bool = False,
        project_context: dict | None = None,
    ) -> AsyncIterator[str]:
        """
        Same generation flow as `generate()`, but yields the final answer as text
        deltas instead of returning it all at once.

        When web search is off, there's no tool-calling decision to make, so we
        stream the answer directly from the first call. When web search is on,
        the initial call still has to be non-streamed (we need the full response
        to know whether the model called the tool) — only the resulting
        answer-producing call is streamed in that case.
        """
        model_messages = self._build_model_messages(
            messages, attachments_context, images, web_search_enabled, project_context
        )
        model_id = config.MODEL_CHOICES.get(model, config.IBM_ICA_MODEL_ID)
        tokens = max_tokens or config.MAX_TOKENS

        if not web_search_enabled:
            try:
                stream_iter = self.client.chat_stream(
                    messages=model_messages,
                    max_tokens=tokens,
                    model_id=model_id,
                )
                async for delta in self._iter_blocking_generator(stream_iter):
                    yield delta
            except IBMICAError as e:
                if getattr(e, "http_code", None) == 429:
                    raise ModelRateLimitError(str(e)) from e
                raise RuntimeError(f"Model generation failed: {str(e)}") from e
            return

        try:
            result = self.client.chat(
                messages=model_messages,
                max_tokens=tokens,
                model_id=model_id,
                tools=[SEARCH_WEB_TOOL],
            )
        except IBMICAError as e:
            if getattr(e, "http_code", None) == 429:
                raise ModelRateLimitError(str(e)) from e
            raise RuntimeError(f"Model generation failed: {str(e)}") from e

        if not result.get("tool_calls"):
            if result["text"]:
                yield result["text"]
            return

        follow_up_messages, all_results = self._prepare_tool_call_followup(model_messages, result)

        try:
            stream_iter = self.client.chat_stream(
                messages=follow_up_messages,
                max_tokens=tokens,
                model_id=model_id,
                tools=[SEARCH_WEB_TOOL],
            )
            async for delta in self._iter_blocking_generator(stream_iter):
                yield delta
        except IBMICAError as e:
            if getattr(e, "http_code", None) == 429:
                raise ModelRateLimitError(str(e)) from e
            raise RuntimeError(f"Model generation failed: {str(e)}") from e

        sources = self._format_sources(all_results)
        if sources:
            yield f"\n\n{sources}"

    @staticmethod
    async def _iter_blocking_generator(gen: Iterator[str]) -> AsyncIterator[str]:
        """Bridge a blocking (network I/O) generator onto the asyncio event loop."""
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def producer():
            try:
                for item in gen:
                    loop.call_soon_threadsafe(queue.put_nowait, ("item", item))
            except Exception as exc:  # noqa: BLE001 - re-raised on the event loop side
                loop.call_soon_threadsafe(queue.put_nowait, ("error", exc))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

        threading.Thread(target=producer, daemon=True).start()

        while True:
            kind, value = await queue.get()
            if kind == "item":
                yield value
            elif kind == "error":
                raise value
            else:
                break

    @staticmethod
    def _format_sources(results: list[dict]) -> str:
        """Build a Markdown 'Sources' section from search results, deduped by URL."""
        seen: set[str] = set()
        links = []
        for r in results:
            url = r.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            title = r.get("title") or url
            links.append(f"{len(links) + 1}. [{title}]({url})")

        if not links:
            return ""

        return "**Sources:**\n" + "\n".join(links)
    
    def _build_model_messages(
        self,
        messages: list[Message],
        attachments_context: str | None = None,
        images: list[dict] | None = None,
        web_search_enabled: bool = False,
        project_context: dict | None = None,
    ) -> list[dict]:
        """Build message list for the model."""
        model_messages = []

        # Add system message: accuracy rules first, then the project, then this message's files
        system_content = BASE_SYSTEM_PROMPT

        if project_context:
            name = project_context.get("name", "")
            if project_context.get("instructions"):
                system_content += (
                    f"\n\n{PROJECT_INSTRUCTION.format(name=name)}\n\n"
                    f"<project_instructions>\n{project_context['instructions']}\n</project_instructions>"
                )
            if project_context.get("documents_context"):
                system_content += (
                    f"\n\n{PROJECT_DOCUMENTS_INSTRUCTION.format(name=name)}\n\n"
                    f"## Project Documents\n\n{project_context['documents_context']}"
                )

        if attachments_context:
            system_content += f"\n\n{ATTACHMENTS_INSTRUCTION}\n\n{attachments_context}"

        if web_search_enabled:
            system_content += f"\n\n{self.ATTRIBUTION_INSTRUCTION}"

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
