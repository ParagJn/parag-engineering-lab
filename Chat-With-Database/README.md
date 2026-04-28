# Chat With Database

A full-stack AI-powered application that lets you converse with your relational database in plain English. Ask questions, explore schemas, run analytics, and get structured results — all without writing a single line of SQL.

---

## Overview

Chat With Database bridges the gap between non-technical users and relational databases by using a large language model (Claude via Anthropic) as an intelligent SQL agent. You describe what you want in natural language; the agent introspects the schema, constructs the right query, executes it, and returns a human-readable answer.

**Supported databases:** PostgreSQL · MySQL

---

## Architecture

```
┌──────────────────────────────────────┐      ┌──────────────────────────────────────┐
│           Frontend (React)           │      │          Backend (FastAPI)            │
│                                      │      │                                      │
│  ConfigScreen  ──► /api/config ──────┼─────►│  POST /api/config                   │
│      (DB credentials form)           │      │    └─ validates connection            │
│                                      │      │    └─ stores SQLAlchemy engine       │
│  ChatInterface ──► /api/chat ────────┼─────►│  POST /api/chat                     │
│      (conversational UI)             │      │    └─ invokes LangGraph ReAct agent  │
│                                      │      │         ├─ get_db_schema_and_tables  │
└──────────────────────────────────────┘      │         ├─ get_table_definition      │
                                              │         └─ execute_sql_query         │
                                              │    └─ returns AI-generated answer    │
                                              └──────────────────────────────────────┘
```

### Backend (`/backend`)

| File | Purpose |
|---|---|
| `main.py` | FastAPI application — routes, CORS, request/response models, error classification |
| `agent.py` | LangGraph ReAct agent — tools, engine registry, LLM initialization |
| `requirements.txt` | Python dependencies |

### Frontend (`/frontend`)

| Path | Purpose |
|---|---|
| `src/components/ConfigScreen.jsx` | Database connection form (host, port, credentials, engine selector) |
| `src/components/ChatInterface.jsx` | Full chat UI with sidebar, markdown rendering, and quick-prompt suggestions |
| `src/lib/api.js` | Typed API client with structured error handling |
| `src/App.jsx` | Root component — manages the config → chat flow |

---

## How It Works

### 1. Database Connection (`ConfigScreen`)

The user fills in connection credentials:
- Database type (PostgreSQL or MySQL)
- Host, port, database name
- Username and password

On submit, the frontend calls `POST /api/config`. The backend:
1. Builds a SQLAlchemy connection URL
2. Creates an engine and tests it with `SELECT 1`
3. Stores the engine in an in-memory session registry
4. Returns a unique `session_id` (UUID) to the frontend

The `session_id` is kept in React state and attached to every subsequent chat request.

### 2. AI Chat Agent (`ChatInterface` + LangGraph)

When the user sends a message, the frontend calls `POST /api/chat` with the message and `session_id`. The backend:

1. Retrieves the correct SQLAlchemy engine from the registry using `session_id`
2. Instantiates a **LangGraph ReAct agent** backed by Claude (`claude-sonnet-4-6` by default)
3. Equips the agent with three tools scoped to that session:

| Tool | What it does |
|---|---|
| `get_db_schema_and_tables_list` | Lists all base tables with their schema names |
| `get_table_definition` | Returns columns, data types, nullability, defaults, and foreign key relationships for a given table |
| `execute_sql_query` | Runs any SQL query and returns the results as JSON |

4. The agent reasons through the request — it first explores the schema, inspects relevant table definitions, constructs a SQL query, executes it, and finally composes a natural language answer
5. The final AI response is returned to the frontend and rendered as Markdown (with syntax-highlighted SQL blocks, formatted tables, etc.)

---

## Tech Stack

### Backend
- **[FastAPI](https://fastapi.tiangolo.com/)** — async Python web framework
- **[LangChain](https://python.langchain.com/) + [LangGraph](https://langchain-ai.github.io/langgraph/)** — ReAct agent orchestration and tool calling
- **[Anthropic Claude](https://www.anthropic.com/)** (`claude-sonnet-4-6`) — the language model powering SQL generation and natural language responses
- **[SQLAlchemy](https://www.sqlalchemy.org/)** — database engine abstraction
- **[psycopg2](https://www.psycopg2.org/)** — PostgreSQL driver
- **[PyMySQL](https://pymysql.readthedocs.io/)** — MySQL driver
- **[python-dotenv](https://pypi.org/project/python-dotenv/)** — environment variable management

### Frontend
- **[React 19](https://react.dev/)** + **[Vite 7](https://vitejs.dev/)** — UI framework and build tool
- **[Tailwind CSS 4](https://tailwindcss.com/)** — utility-first styling
- **[Framer Motion](https://www.framer.com/motion/)** — page and component animations
- **[react-markdown](https://github.com/remarkjs/react-markdown)** + **[remark-gfm](https://github.com/remarkjs/remark-gfm)** — Markdown rendering with table support
- **[react-syntax-highlighter](https://github.com/react-syntax-highlighter/react-syntax-highlighter)** — syntax-highlighted SQL code blocks
- **[Lucide React](https://lucide.dev/)** — icon library

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- A running PostgreSQL or MySQL instance
- An [Anthropic API key](https://console.anthropic.com/)

---

### Backend Setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows

# Install dependencies
pip install -r requirements.txt

# Create the environment file
cp .env.example .env            # or create it manually (see below)
```

Create `backend/.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
# Optional: override the default model
# ANTHROPIC_MODEL=claude-sonnet-4-6
```

Start the backend:

```bash
uvicorn main:app --reload
# Runs on http://localhost:8000
```

---

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Optional: configure a custom API base URL
# Create frontend/.env.local and add:
# VITE_API_BASE_URL=http://localhost:8000

# Start the dev server
npm run dev
# Runs on http://localhost:5173
```

---

### Using the App

1. Open `http://localhost:5173` in your browser
2. Fill in your database credentials on the connection screen and click **Connect**
3. Once connected, the chat interface opens — ask anything in plain English:
   - *"List all tables in the database"*
   - *"Give me an overview of the database schema"*
   - *"Show the row count for every table"*
   - *"How many orders were placed last month?"*
   - *"Show me the top 10 customers by total spend"*
4. The AI will introspect the schema, write the SQL, run it, and explain the results
5. Click **Disconnect** (power icon) to return to the connection screen

---

## API Reference

### `POST /api/config`

Validates database credentials and returns a session identifier.

**Request body:**
```json
{
  "db_type": "postgres",
  "host": "localhost",
  "port": 5432,
  "user": "myuser",
  "password": "mypassword",
  "db_name": "mydb"
}
```

**Response (`200 OK`):**
```json
{
  "session_id": "3f8a1b2c-...",
  "message": "Database configured successfully."
}
```

**Error response (`400`):** Structured error with `code`, `title`, `message`, `suggestions`, `issues`, and `technical_details`.

---

### `POST /api/chat`

Sends a user message to the AI agent and returns the response.

**Request body:**
```json
{
  "session_id": "3f8a1b2c-...",
  "message": "What are the 5 most recent orders?"
}
```

**Response (`200 OK`):**
```json
{
  "session_id": "3f8a1b2c-...",
  "response": "Here are the 5 most recent orders:\n\n| order_id | customer | total | created_at |\n..."
}
```

**Error codes:**

| HTTP | Code | Cause |
|---|---|---|
| 401 | `session_not_found` | Session ID is missing or backend was restarted |
| 500 | `missing_ai_api_key` | `ANTHROPIC_API_KEY` not set in `.env` |
| 500 | `invalid_ai_api_key` | API key was rejected by Anthropic |
| 500 | `ai_rate_limited` | Anthropic API rate limit exceeded |
| 500 | `chat_processing_failed` | Generic agent or execution error |

---

## Project Structure

```
Chat-With-Database/
├── backend/
│   ├── agent.py          # LangGraph ReAct agent, tools, engine registry
│   ├── main.py           # FastAPI routes, error handling, request models
│   └── requirements.txt  # Python dependencies
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx              # Root component, config↔chat state machine
        ├── main.jsx             # React app entry point
        ├── App.css / index.css  # Global styles
        ├── components/
        │   ├── ConfigScreen.jsx # DB connection form
        │   └── ChatInterface.jsx# Chat UI, sidebar, message list
        └── lib/
            └── api.js           # Typed API client, error normalization
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Your Anthropic API key |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-6` | Model name to use |

### Frontend (`frontend/.env.local`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `VITE_API_BASE_URL` | No | `http://localhost:8000` | Backend API base URL |

---

## Notes & Limitations

- **Session storage is in-memory.** If the backend process restarts, all active sessions are lost. Reconnect from the UI to create a new session.
- **CORS is open (`allow_origins=["*"]`)** — suitable for local development and demos only. For production, restrict to your frontend's origin.
- **No write protection** — the agent can execute any SQL, including `INSERT`, `UPDATE`, or `DELETE` if asked. Consider restricting the database user to `SELECT` only for read-only use cases.
- Only **PostgreSQL** and **MySQL** are currently supported.
