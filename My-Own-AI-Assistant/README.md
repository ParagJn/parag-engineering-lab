# My Own AI Assistant

A clean, modern AI chat assistant application that leverages IBM's ICA (watsonx Code Assistant) model infrastructure. Built for internal use as a personal productivity tool for technical work and document analysis.

## Overview

This is a full-stack web application that provides a ChatGPT-like experience using IBM's enterprise AI infrastructure. It features a sleek React frontend with conversation management and a FastAPI backend that handles document processing, web search, and AI interactions.

## Key Features

- **💬 Chat Interface**: Clean, modern UI inspired by popular AI assistants
- **⚡ Live Streaming**: Assistant replies stream in token-by-token instead of appearing all at once, with a graceful fallback to a single chunk if the model gateway doesn't support SSE for a given request
- **🌐 Web Search**: Optional per-session toggle that lets the model call a DuckDuckGo-backed search tool for up-to-date information; web-sourced sentences are visually highlighted in the reply and a "Sources" list is appended
- **🧠 Model Choice**: Switch between model providers (Claude, Gemini) per session
- **📂 Session Management**: Create, rename, and organize multiple conversations
- **📄 Document Upload**: Supports text files, Markdown, PDFs, and Word documents, including image extraction from documents for vision analysis
- **⬇️ Download Replies**: Save any assistant response as a `.md` file with one click
- **⏳ Rate-Limit Handling**: If the model gateway returns HTTP 429, the UI shows a countdown and automatically retries, with an option to cancel and restore your message
- **🎨 Modern Design**: Beautiful gradient themes and smooth animations
- **💾 Persistent Storage**: All conversations saved locally in JSON format
- **🖥️ Code Highlighting**: Syntax-highlighted code blocks with copy functionality

## Tech Stack

**Frontend:**
- React 19 with TypeScript
- Vite for fast builds
- TailwindCSS for styling
- React Markdown with syntax highlighting (GFM + sanitized raw HTML for source attribution)
- Native `fetch` streaming (Server-Sent Events) for live responses
- Axios for non-streaming API communication

**Backend:**
- FastAPI (Python)
- IBM ICA Client (watsonx Code Assistant) — a hand-rolled `urllib`-based HTTP/SSE client with multi-endpoint fallback
- DuckDuckGo Search (`ddgs`) for the web search tool
- PyPDF2 for PDF extraction
- python-docx for Word document processing
- JSON-based file storage

## Prerequisites

- Python 3.11+
- Node.js 18+
- IBM ICA API credentials

## Installation

### 1. Clone and Navigate

```bash
cd My-Own-AI-Assistant
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file in the `backend` directory:

```env
IBM_ICA_API_KEY=your_api_key_here
IBM_ICA_ENDPOINT=https://your-ibm-ica-endpoint
IBM_ICA_MODEL_ID=claude-opus-5-5
IBM_ICA_GEMINI_MODEL_ID=gemini-3.7-flash
IBM_ICA_INSECURE_TLS=false
```

### 4. Frontend Setup

```bash
cd ../frontend
npm install
```

## Running the Application

Use the provided startup script:

```bash
chmod +x start.sh
./start.sh
```

Or start services manually:

**Backend:**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm run dev
```

Access the application at `http://localhost:5173`

## Usage

1. **Start a Conversation**: Click "New Conversation" to begin
2. **Pick a Model**: Choose the model provider (Claude/Gemini) from the composer
3. **Toggle Web Search**: Enable it when you need current/external information; the model decides on its own whether a given question actually needs a search
4. **Upload Documents**: Click the attach button to upload .txt, .md, .pdf, or .docx files
5. **Ask Questions**: Type your message and press Enter (Shift+Enter for new lines) — the reply streams in as it's generated
6. **Download a Reply**: Hover the download icon next to any assistant reply to save it as a `.md` file
7. **Rename Sessions**: Hover over any conversation and click the edit icon to rename
8. **Delete Sessions**: Click the trash icon to remove conversations

## File Structure

```
My-Own-AI-Assistant/
├── backend/
│   ├── app/
│   │   ├── models/          # Data models
│   │   ├── repositories/    # Data persistence
│   │   ├── routers/         # API endpoints (sessions, messages, attachments)
│   │   ├── services/        # Business logic (model, web search, message, session, attachment, extraction)
│   │   ├── ibm_ica_client.py  # Reusable IBM ICA client (chat + streaming)
│   │   └── main.py          # FastAPI app
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # React components (ChatWindow, Message, Composer, Sidebar, RateLimitTimer)
│   │   ├── services/        # API client (axios + streaming fetch)
│   │   └── types/           # TypeScript types
│   └── package.json
├── data/                    # Storage directory
│   ├── sessions/            # Conversation history
│   └── documents/           # Uploaded files
└── start.sh                 # Startup script
```

## Features in Detail

### Session Management
- Create unlimited conversation sessions
- Rename conversations inline
- Automatic title generation from first message
- Per-session model choice and web-search toggle, persisted with the session
- Organized by date (Today, Yesterday, Earlier)
- Persistent storage in JSON format

### Streaming Responses
- Replies are streamed over Server-Sent Events and rendered incrementally as they arrive
- If web search is off, the answer streams from the very first model call
- If web search is on, the model first makes a (non-streamed) decision on whether to call the search tool; once that resolves, the actual answer still streams in
- If the model gateway ignores the streaming request and returns a single response body instead, the app falls back to displaying the full reply in one update — streaming degrades gracefully rather than breaking the chat

### Web Search
- Model can call a `search_web` tool (backed by DuckDuckGo via `ddgs`) when it needs current information
- Sentences/facts drawn from search results are wrapped and highlighted (`web-sourced` styling) to distinguish them from the model's own knowledge or uploaded documents
- A deduplicated "Sources" list with links is appended to the reply

### Document Processing
- **Text Files**: Direct content reading
- **Markdown**: Preserved formatting
- **PDFs**: Page-by-page text extraction
- **Word Documents**: Full paragraph extraction, including embedded images for vision analysis
- Attachments linked to specific messages

### Downloading Replies
- Every assistant message has a download icon that saves its content as a `.md` file (Markdown only — no PDF/DOCX export)

### Rate-Limit (429) Handling
- If the model provider rate-limits a request, the UI shows a countdown timer and automatically retries once
- The user can cancel the wait, which restores their message to the composer instead of losing it

### AI Capabilities
- Powered by Claude Opus 5.5 (or Gemini) via IBM ICA
- Context-aware conversations
- Document analysis and summarization
- Optional web search grounding
- Code generation and explanation
- Technical Q&A

## Configuration

### Model Settings
Adjust in `backend/app/config.py`:
- `MODEL_CHOICES`: Maps a provider key (`claude`, `gemini`) to its underlying model ID
- `MAX_TOKENS`: Maximum response length (default: 100,000)
- `MODEL_TIMEOUT`: API timeout in seconds (default: 180)
- `MAX_FILE_SIZE`: Upload limit (default: 5MB)

### Supported File Types
- `.txt` - Plain text
- `.md`, `.markdown` - Markdown
- `.pdf` - PDF documents
- `.doc`, `.docx` - Word documents

## API Endpoints

### Sessions
- `POST /api/sessions` - Create new session
- `GET /api/sessions` - List all sessions
- `GET /api/sessions/{id}` - Get session details
- `PATCH /api/sessions/{id}` - Rename session, change model, or toggle web search
- `DELETE /api/sessions/{id}` - Delete session

### Messages
- `POST /api/sessions/{id}/messages` - Send message, get the full response
- `POST /api/sessions/{id}/messages/stream` - Send message, stream the response back as Server-Sent Events

### Attachments
- `POST /api/sessions/{id}/attachments` - Upload file
- `GET /api/sessions/{id}/attachments/{id}` - Get attachment

## Notes

- **Internal Use Only**: This tool is built for personal productivity and internal technical work
- **Rate Limits**: IBM ICA API has rate limits; the app handles 429s with an automatic countdown/retry, but you may still need to wait between bursts of requests
- **Storage**: All data stored locally in the `data/` directory
- **Security**: Keep your `.env` file secure and never commit it to version control

## Troubleshooting

**"Failed to send message" errors:**
- Check your IBM ICA credentials in `.env`
- Verify the endpoint is accessible
- Wait if you're hitting rate limits (HTTP 429) — the countdown timer will retry automatically

**No streaming / reply appears all at once:**
- This means the model gateway ignored the streaming request for that call and the app fell back to a single-chunk update — this is expected fallback behavior, not an error
- Check backend console logs (INFO level) from `ibm_ica_client.chat_stream` for whether real SSE data was detected

**Build errors:**
- Ensure Node.js 18+ and Python 3.11+ are installed
- Delete `node_modules` and `package-lock.json`, then reinstall
- Check that all dependencies in `requirements.txt` are installed

**Upload failures:**
- Verify file size is under 5MB
- Ensure file type is supported (.txt, .md, .pdf, .doc, .docx)
- Check the `data/documents` directory exists

## License

Internal use for demo only - Not for public distribution
