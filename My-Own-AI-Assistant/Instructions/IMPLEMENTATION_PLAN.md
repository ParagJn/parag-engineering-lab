# Implementation Plan

## Phase 1 — Repository inspection

Before modifying anything:

```bash
pwd
ls
find . -maxdepth 2 -type f | sort
```

Check Python:

```bash
/Users/paragjain/dev-works/myenv/bin/python --version
/Users/paragjain/dev-works/myenv/bin/pip --version
```

Check whether Node/npm are available:

```bash
node --version
npm --version
```

Inspect existing frontend/backend before creating files.

## Phase 2 — Backend foundation

Create:

```text
backend/app/
├── main.py
├── config.py
├── models/
│   ├── session.py
│   ├── message.py
│   └── attachment.py
├── routers/
│   ├── sessions.py
│   ├── messages.py
│   └── attachments.py
├── services/
│   ├── session_service.py
│   ├── message_service.py
│   ├── attachment_service.py
│   ├── extraction_service.py
│   └── model_service.py
└── repositories/
    ├── session_repository.py
    └── attachment_repository.py
```

Keep implementation straightforward.

## Phase 3 — JSON persistence

Implement:

- create session
- list sessions
- get session
- save session
- delete session
- append message

Use atomic writes.

Add repository-level tests.

## Phase 4 — Model adapter

Implement a provider interface.

Prefer an OpenAI-compatible HTTP adapter if the user's model server exposes that interface.

Configuration:

```env
MODEL_PROVIDER=custom
MODEL_NAME=your-model
MODEL_BASE_URL=http://localhost:8000/v1
MODEL_API_KEY=
```

Do not assume these exact values will be used. Read configuration from `.env`.

If no model is configured, return a clear configuration error rather than crashing at application startup.

## Phase 5 — Document extraction

Implement separate extractors:

```text
PDFExtractor
DocxExtractor
TextExtractor
MarkdownExtractor
ImageExtractor
```

Use a common interface.

Example conceptual interface:

```python
class DocumentExtractor(Protocol):
    def supports(self, mime_type: str, filename: str) -> bool:
        ...

    def extract(self, path: Path) -> str:
        ...
```

Store extracted Markdown separately from the original file.

## Phase 6 — Context construction

Create a dedicated context builder.

Conceptually:

```python
context = context_builder.build(
    session=session,
    current_message=user_message,
    attachment_ids=attachment_ids,
)
```

The context builder should:

1. Add system instructions.
2. Add historical messages.
3. Add relevant attachment content.
4. Add current user message.

Do not bury this logic inside the FastAPI route.

## Phase 7 — Frontend

Recommended stack:

- React
- TypeScript
- Vite
- Tailwind CSS
- react-markdown
- remark-gfm
- a syntax highlighter such as Shiki or Prism-based tooling

Build:

```text
App
├── Sidebar
│   ├── NewSessionButton
│   └── SessionList
├── ChatWindow
│   ├── EmptyState
│   ├── MessageList
│   │   └── Message
│   └── Composer
│       ├── AttachmentButton
│       ├── AttachmentPreview
│       └── SendButton
```

## Phase 8 — Integration

Connect:

```text
React
  |
  +-- GET /api/sessions
  +-- POST /api/sessions
  +-- GET /api/sessions/{id}
  +-- POST /api/sessions/{id}/attachments
  +-- POST /api/sessions/{id}/messages
```

Ensure backend remains the source of truth.

## Phase 9 — UX refinement

Add:

- Auto-scroll
- Keyboard shortcut for send
- Shift+Enter for newline
- Disabled send while empty
- Loading indicator
- Upload state
- Retry for transient request failure
- Copy code
- Clean typography
- Responsive sidebar

## Phase 10 — Testing

Run backend tests.

Run frontend lint/typecheck/tests.

Start both services and manually test:

### Test A — context

```text
User: My favorite language is Python.
Assistant: ...
User: What language did I say I like?
```

Expected: Python.

### Test B — persistence

1. Create session.
2. Send messages.
3. Stop backend.
4. Restart backend.
5. Load session.
6. Verify messages exist.
7. Ask contextual question.

### Test C — document

1. Upload PDF.
2. Confirm Markdown extraction.
3. Ask a question about it.
4. Verify model receives attachment context.

### Test D — isolation

1. Create session A.
2. Add unique fact.
3. Create session B.
4. Ask B about A's fact.

Expected: B must not inherit A's context.

## Phase 11 — Run instructions

Backend:

```bash
source /Users/paragjain/dev-works/myenv/bin/activate
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Use a Vite proxy or environment variable for the backend URL.

## Final validation

The coding agent must report:

- What was created
- What was changed
- Backend start command
- Frontend start command
- Model configuration
- Supported file types
- Test results
- Known limitations
