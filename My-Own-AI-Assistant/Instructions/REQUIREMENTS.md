# Functional Requirements

## 1. Conversation sessions

### FR-001 — New session

The user can click **New Session**.

The backend creates a unique session ID and returns it.

The new session starts with an empty message list.

### FR-002 — Existing sessions

The application displays previously persisted sessions in the sidebar.

Each session should display:

- Short title or first meaningful message
- Updated timestamp

### FR-003 — Load session

Selecting a session loads its JSON history and displays the conversation.

The backend remains the source of truth.

### FR-004 — Context continuity

If the user sends:

> My project is called Alpha.

and later:

> What is my project called?

the model should be given sufficient persisted context to answer:

> Alpha.

This must continue to work after the application is restarted and the session is loaded again.

## 2. Messages

### FR-005 — User message

A user can submit text.

### FR-006 — Assistant response

The backend invokes the configured model and stores its response.

### FR-007 — Message IDs

Every message receives a unique message ID.

### FR-008 — Ordering

Messages retain their chronological order.

## 3. Documents

### FR-009 — Upload

The user can attach a supported document.

### FR-010 — Extraction

The backend extracts meaningful content.

### FR-011 — Markdown representation

The extracted content is stored as Markdown.

### FR-012 — Conversation reference

The message/session history must retain the attachment ID and filename so the conversation can reference it later.

### FR-013 — Document questions

The user can ask questions about an uploaded document.

## 4. Images

### FR-014 — Image upload

The user can upload an image.

### FR-015 — Image processing

The system should represent image content through the model abstraction.

If the configured model supports vision, pass the image appropriately.

If it does not, use a pluggable OCR/vision adapter.

Do not hard-code vision behavior into the chat router.

## 5. UI

### FR-016 — Chat interface

The UI should resemble a modern AI chat application without attempting to clone proprietary branding.

### FR-017 — Markdown

Assistant output supports Markdown.

### FR-018 — Code

Code blocks are syntax highlighted.

### FR-019 — Copy code

Each fenced code block has a copy action.

### FR-020 — Attachments

Attached files are visible in the relevant message/composer area.

### FR-021 — Loading

The UI clearly indicates when a message is being generated.

### FR-022 — Errors

Model/backend errors are shown without losing the user's unsent text.

## 6. Persistence

### FR-023 — JSON only

Use JSON files for version 1 persistence.

### FR-024 — Restart resilience

Restarting the backend must not delete session history.

### FR-025 — Atomic persistence

Avoid corrupting history if a write is interrupted.

## 7. Non-functional requirements

### NFR-001

Code should be modular.

### NFR-002

Frontend and backend should be independently runnable.

### NFR-003

Configuration must come from environment variables where appropriate.

### NFR-004

The model provider must be replaceable.

### NFR-005

The application should be usable on a laptop without external infrastructure.

### NFR-006

The first version should favor simplicity over premature scalability.
