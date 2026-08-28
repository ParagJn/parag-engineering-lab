# Architecture

## High-level architecture

```text
                    ┌──────────────────────────┐
                    │       React + Tailwind   │
                    │                          │
                    │  Sidebar                │
                    │  Conversation           │
                    │  Composer + Upload       │
                    └────────────┬─────────────┘
                                 │ HTTP/JSON
                                 │
                    ┌────────────▼─────────────┐
                    │          FastAPI         │
                    │                          │
                    │  Session API             │
                    │  Message API             │
                    │  Attachment API          │
                    └──────┬─────────┬─────────┘
                           │         │
             ┌─────────────▼───┐ ┌──▼────────────────┐
             │ Session Store   │ │ Attachment Service│
             │ JSON files      │ │ extraction        │
             └─────────────┬───┘ └──┬────────────────┘
                           │         │
                           │         ▼
                           │    Markdown files
                           │
             ┌─────────────▼─────────────────────────┐
             │              Model Service             │
             │                                       │
             │  Provider Adapter                     │
             │  Local/custom/OpenAI-compatible API   │
             └───────────────────────────────────────┘
```

## Request flow

### Normal chat

```text
User
 |
 | POST /sessions/{id}/messages
 v
FastAPI
 |
 v
Load JSON session
 |
 v
Append user message in memory
 |
 v
Build model context
 |
 v
Model Provider
 |
 v
Assistant response
 |
 v
Append assistant message
 |
 v
Atomic JSON save
 |
 v
Return response
```

### Document upload

```text
Browser
 |
 | multipart upload
 v
FastAPI
 |
 v
Validate file
 |
 v
Store original file
 |
 v
Extractor
 |
 v
Markdown
 |
 +----> data/documents/<attachment_id>/content.md
 |
 v
Return attachment metadata
```

### Document conversation

The assistant should receive both:

1. Normal conversation context.
2. Relevant attachment Markdown/context.

For version 1, when an attachment is explicitly associated with the current message, include its extracted Markdown in the model request.

A later version can introduce retrieval/chunking if documents become too large.

## Suggested data layout

```text
data/
├── sessions/
│   ├── sess_abc.json
│   └── sess_xyz.json
└── documents/
    ├── att_123/
    │   ├── original.pdf
    │   └── content.md
    └── att_456/
        ├── original.png
        └── content.md
```

## Why JSON first?

JSON is appropriate for the initial single-user implementation because:

- Easy to inspect manually
- Easy to back up
- No database setup
- Easy to debug
- Session ID maps naturally to a file
- Sufficient for a personal/local assistant

The repository interface should make it possible to replace JSON with SQLite later without changing API behavior.

## Context strategy

The initial context should be:

```text
system instructions
+
conversation history
+
current attachment context
+
current user message
```

Do not store a second independently maintained "conversation summary" unless needed.

A future optimization can add:

```text
recent messages
+
rolling summary
+
retrieved document chunks
```

but this is not required for version 1.

## Important architectural boundary

The model adapter must know how to talk to the model.

The session service must NOT know how the model is hosted.

This allows the same application to work with:

- local inference server
- OpenAI-compatible server
- custom HTTP API
- future hosted provider
