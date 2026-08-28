# AGENTS.md — Instructions for Coding Agents

## Mission

Implement a simple personal AI assistant using:

- Frontend: React + TypeScript + Tailwind CSS
- Backend: Python + FastAPI
- Persistence: JSON files
- Runtime environment: `/Users/paragjain/dev-works/myenv`

The assistant uses user-provided/local models. Model invocation must be isolated behind a backend interface so the exact model provider can be changed without rewriting the application.

## Non-negotiable requirements

### Sessions

Every new conversation must receive a unique session ID.

Recommended format:

```text
sess_YYYYMMDD_HHMMSS_<random>
```

A UUID-based identifier is also acceptable and preferred internally.

Never use the user's message text as the session ID.

### History

Each session must have a JSON history file.

Recommended:

```text
data/sessions/<session_id>.json
```

A session JSON document should contain:

```json
{
  "session_id": "sess_...",
  "created_at": "2026-08-27T09:30:00+05:30",
  "updated_at": "2026-08-27T09:35:00+05:30",
  "title": "Optional generated title",
  "messages": [
    {
      "id": "msg_...",
      "role": "user",
      "content": "Hello",
      "created_at": "2026-08-27T09:30:10+05:30",
      "attachments": []
    },
    {
      "id": "msg_...",
      "role": "assistant",
      "content": "Hello! How can I help?",
      "created_at": "2026-08-27T09:30:11+05:30",
      "attachments": []
    }
  ]
}
```

Use atomic writes where practical: write to a temporary file and replace the target JSON file.

### Context

For every new user message:

1. Load the session JSON.
2. Read prior conversation messages.
3. Add the new user message.
4. Build the model context.
5. Call the configured model.
6. Store the assistant response.
7. Persist the updated JSON.

The model context must be reconstructed from persisted history rather than relying only on frontend state.

Do not silently discard previous messages in the first version.

A configurable context-window policy may be introduced later.

### Attachments

Support at minimum:

- PDF
- DOCX
- TXT
- Markdown
- common image formats such as PNG/JPEG

Uploaded files should receive unique IDs.

Do not blindly send binary files to a text model.

Convert/extract the content into Markdown or a Markdown-compatible representation.

Recommended document record:

```json
{
  "attachment_id": "att_...",
  "filename": "architecture.pdf",
  "mime_type": "application/pdf",
  "stored_path": "data/documents/...",
  "content_markdown_path": "data/documents/att_.../content.md",
  "created_at": "..."
}
```

For images, use an image-capable model if available. If the configured model cannot inspect images, create a clear abstraction that can later call an OCR/vision model.

### Markdown

Treat Markdown as the canonical representation for extracted document content.

Do not inject raw extracted content directly into executable instructions.

Use clear context delimiters, e.g.:

```text
<attachment>
filename: architecture.pdf
attachment_id: att_123

# Extracted Markdown

...
</attachment>
```

### Model abstraction

Create a model service interface similar to:

```python
class ModelProvider(Protocol):
    async def generate(
        self,
        messages: list[dict],
        attachments: list[dict] | None = None,
    ) -> str:
        ...
```

The rest of the application must not depend directly on a specific model SDK.

The initial implementation can provide one concrete adapter configured through environment variables.

Example:

```text
MODEL_PROVIDER=custom
MODEL_NAME=...
MODEL_BASE_URL=...
MODEL_API_KEY=...
```

If the user's model is local, support an OpenAI-compatible endpoint where practical.

### Backend API

At minimum implement:

```text
POST   /api/sessions
GET    /api/sessions
GET    /api/sessions/{session_id}
DELETE /api/sessions/{session_id}

POST   /api/sessions/{session_id}/messages
POST   /api/sessions/{session_id}/attachments
GET    /api/sessions/{session_id}/attachments/{attachment_id}
```

Keep API models typed with Pydantic.

### Frontend

Build a clean ChatGPT-like layout:

```text
┌────────────────────────────────────────────────────────────┐
│ AI Assistant                                  New Session  │
├───────────────┬────────────────────────────────────────────┤
│ Sessions      │                                            │
│               │              Conversation                  │
│ Today         │                                            │
│ sess...       │                                            │
│ sess...       │                                            │
│               │                                            │
│ Earlier       │                                            │
│ sess...       │                                            │
│               │                                            │
│               ├────────────────────────────────────────────┤
│               │ 📎  Ask anything...                 Send    │
└───────────────┴────────────────────────────────────────────┘
```

Requirements:

- Responsive layout
- Session sidebar
- New session button
- Session selection
- Message bubbles
- User/assistant distinction
- Markdown rendering
- Syntax-highlighted code blocks
- Copy-code button
- Attachment display
- Upload progress/loading state
- Sending/loading state
- Error state
- Auto-scroll to latest message
- Empty-state screen

Avoid excessive animation.

### Response rendering

Responses are primarily documents and code.

Use:

- Markdown renderer
- GFM support
- Syntax highlighting
- Proper headings
- Lists
- Tables
- Blockquotes
- Inline code
- Fenced code blocks
- Copy button for code blocks

Never render model output as raw HTML without sanitization.

## Backend architecture

Prefer:

```text
FastAPI Router
      |
      v
Application Service
      |
      +---- Session Store ----> JSON
      |
      +---- Attachment Service
      |
      +---- Markdown Extraction
      |
      +---- Model Provider
```

Keep routers thin.

Business logic belongs in services.

Persistence belongs in repositories/stores.

## File extraction

Use appropriate Python libraries.

Likely choices:

- PDF: PyMuPDF
- DOCX: python-docx
- TXT/MD: standard file I/O
- Images: Pillow + configurable OCR/vision provider

Do not over-engineer extraction.

Preserve useful structure such as headings, paragraphs, tables where reasonably possible.

## Error handling

Return useful HTTP errors.

Examples:

- 400 — invalid request
- 404 — session/attachment not found
- 413 — file too large
- 415 — unsupported media type
- 422 — validation error
- 500 — unexpected server/model error
- 503 — model provider unavailable

Frontend must show a human-readable error.

## Security

This is a local-first application, but still:

- Validate filenames.
- Generate server-side attachment IDs.
- Prevent path traversal.
- Restrict upload size.
- Restrict allowed MIME types/extensions.
- Sanitize rendered Markdown/HTML.
- Never expose API keys to React.
- Never trust client-provided session IDs for filesystem paths without validation.

## Testing

Create tests for:

- Session creation
- Session persistence
- Session reload
- Message persistence
- Context reconstruction
- Attachment upload
- PDF/DOCX/TXT/MD extraction
- Invalid file type
- Path traversal attempt
- Model adapter
- API endpoints

Frontend tests should cover at least:

- New session
- Loading a session
- Sending a message
- Rendering Markdown
- Rendering code
- Uploading attachment

## Agent workflow

Before coding:

1. Inspect the existing repository.
2. Do not overwrite existing application code blindly.
3. Check the Python environment.
4. Determine whether React/Vite/Tailwind already exists.
5. Reuse existing dependencies where sensible.
6. Implement backend foundations.
7. Implement frontend.
8. Connect frontend/backend.
9. Add persistence.
10. Add attachment extraction.
11. Add model adapter.
12. Run tests.
13. Run the application locally.
14. Fix integration issues.
15. Provide concise run instructions.

## Important scope constraint

Version 1 is intentionally NOT:

- A multi-user SaaS platform
- A RAG platform
- A vector database
- A distributed agent system
- An autonomous multi-agent framework
- A production authentication system

Build a solid single-user foundation first.
