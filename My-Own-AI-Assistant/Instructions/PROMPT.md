# Master Build Prompt

You are an expert full-stack engineer.

Build the application described by this repository specification.

## Objective

Create a simple personal AI assistant with a ChatGPT-like UI, using the user's own model(s).

The application must use:

- React
- TypeScript
- Tailwind CSS
- FastAPI
- Python
- JSON-file persistence

Python must use this existing virtual environment:

`/Users/paragjain/dev-works/myenv`

## Core behavior

A user can:

1. Create a new session.
2. Receive a unique session ID.
3. Chat with the configured model.
4. Upload documents.
5. Upload images.
6. Convert/extract uploaded content into Markdown where appropriate.
7. Ask questions about uploaded content.
8. Continue a conversation with retained context.
9. Close/restart the application.
10. Load an existing session.
11. Continue that session with the same context.
12. View model output as high-quality Markdown and formatted code.

## Persistence requirement

Every session must be represented by a JSON file:

```text
data/sessions/<session_id>.json
```

The backend must reconstruct model context from the persisted session.

Do not make frontend state the authoritative source of conversation history.

## Attachments

Store original uploaded files separately from extracted Markdown.

Use attachment IDs.

Never rely on filenames as identifiers.

At minimum support:

- PDF
- DOCX
- TXT
- MD
- PNG/JPEG

## UI

Create a clean, modern interface:

- Left session sidebar
- New Session
- Existing session list
- Main conversation
- Attachment controls
- Composer
- Send button
- Markdown rendering
- Syntax highlighting
- Copy code
- Loading/error states

Do not over-design it.

The primary use case is technical work involving documents and code.

## Architecture

Separate:

- API routes
- business/application services
- repositories
- document extraction
- model provider
- frontend API client
- UI components

Use dependency injection where it genuinely improves testability, but do not create unnecessary abstractions.

## Model integration

The exact model is intentionally unspecified.

Implement a model provider abstraction.

Prefer compatibility with an OpenAI-style API if the user's model server supports it.

Read configuration from environment variables.

Do not put model credentials in the frontend.

## Important engineering constraints

- No database for version 1.
- No Redis.
- No vector database.
- No authentication.
- No Kubernetes.
- No unnecessary agent framework.
- No premature microservices.
- No hard-coded absolute paths except configuration/defaults for the requested Python environment.
- No hard-coded model provider.
- No raw unsanitized HTML rendering.
- No path traversal vulnerabilities.

## Development process

First inspect the existing project.

Then:

1. Establish backend.
2. Establish persistence.
3. Establish model abstraction.
4. Establish extraction.
5. Establish APIs.
6. Establish frontend.
7. Integrate.
8. Test.
9. Run locally.
10. Fix issues.
11. Document how to run it.

Do not stop after generating scaffolding. The final result should be runnable.

## Success criterion

The final application should feel like a small, focused personal ChatGPT-style workspace for technical/document work, while keeping the implementation simple enough that another developer can understand the entire system.
