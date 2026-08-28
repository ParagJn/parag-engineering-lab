# Personal AI Assistant — Build Specification

## Goal

Build a simple, local-first AI assistant with a ChatGPT-like experience using the user's own models.

The application must support:

- Text chat
- Document upload
- Image upload
- Conversion of uploaded documents/images into Markdown for model interaction
- Persistent chat history stored as JSON
- Unique session ID for every conversation
- Loading existing sessions
- Creating new sessions
- Context retention across turns
- Document/code-oriented response rendering
- React + Tailwind CSS frontend
- FastAPI Python backend
- User-specified Python virtual environment:

`/Users/paragjain/dev-works/myenv`

## Design principle

Keep the first version deliberately simple.

Do not introduce a database, Redis, vector database, authentication system, microservices, Kubernetes, or a complicated agent framework unless a later requirement explicitly needs one.

The first version should be understandable, debuggable, and easy to extend.

## Recommended repository structure

```text
ai-assistant/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types/
│   │   └── App.tsx
│   ├── package.json
│   └── ...
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models/
│   │   ├── routers/
│   │   ├── services/
│   │   └── utils/
│   ├── storage/
│   │   ├── sessions/
│   │   └── documents/
│   └── requirements.txt
├── data/
│   ├── sessions/
│   └── documents/
├── .env.example
├── AGENTS.md
└── README.md
```

## Runtime

Use the existing virtual environment:

```bash
source /Users/paragjain/dev-works/myenv/bin/activate
```

Do not create a second Python virtual environment unless explicitly requested.

## Definition of done

The user can:

1. Start the backend.
2. Start the frontend.
3. Create a new session.
4. Receive a generated unique session ID.
5. Send multiple messages and have previous messages retained as context.
6. Upload a supported document.
7. Upload an image.
8. See uploaded content represented as Markdown/context.
9. Ask questions about uploaded content.
10. Receive well-formatted Markdown/code responses.
11. Close/reopen the application and load an existing session.
12. See the same conversation context after loading that session.
13. Create another session without affecting the previous session.
