# My Own AI Assistant

A clean, modern AI chat assistant application that leverages IBM's ICA (watsonx Code Assistant) model infrastructure. Built for internal use as a personal productivity tool for technical work and document analysis.

## Overview

This is a full-stack web application that provides a ChatGPT-like experience using IBM's enterprise AI infrastructure. It features a sleek React frontend with conversation management and a FastAPI backend that handles document processing and AI interactions.

## Key Features

- **💬 Chat Interface**: Clean, modern UI inspired by popular AI assistants
- **📂 Session Management**: Create, rename, and organize multiple conversations
- **📄 Document Upload**: Supports text files, Markdown, PDFs, and Word documents
- **🎨 Modern Design**: Beautiful gradient themes and smooth animations
- **💾 Persistent Storage**: All conversations saved locally in JSON format
- **🔄 Real-time Streaming**: Fast response rendering with markdown support
- **🖥️ Code Highlighting**: Syntax-highlighted code blocks with copy functionality

## Tech Stack

**Frontend:**
- React 18 with TypeScript
- Vite for fast builds
- TailwindCSS for styling
- React Markdown with syntax highlighting
- Axios for API communication

**Backend:**
- FastAPI (Python)
- IBM ICA Client (watsonx Code Assistant)
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
IBM_ICA_MODEL_ID=claude-sonnet-5
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
2. **Upload Documents**: Click the attach button to upload .txt, .md, .pdf, or .docx files
3. **Ask Questions**: Type your message and press Enter (Shift+Enter for new lines)
4. **Rename Sessions**: Hover over any conversation and click the edit icon to rename
5. **Delete Sessions**: Click the trash icon to remove conversations

## File Structure

```
My-Own-AI-Assistant/
├── backend/
│   ├── app/
│   │   ├── models/          # Data models
│   │   ├── repositories/    # Data persistence
│   │   ├── routers/         # API endpoints
│   │   ├── services/        # Business logic
│   │   └── main.py          # FastAPI app
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── services/        # API client
│   │   └── types/           # TypeScript types
│   └── package.json
├── data/                    # Storage directory
│   ├── sessions/            # Conversation history
│   └── documents/           # Uploaded files
├── ibm_ica_client.py        # Reusable IBM ICA client
└── start.sh                 # Startup script
```

## Features in Detail

### Session Management
- Create unlimited conversation sessions
- Rename conversations inline
- Automatic title generation from first message
- Organized by date (Today, Yesterday, Earlier)
- Persistent storage in JSON format

### Document Processing
- **Text Files**: Direct content reading
- **Markdown**: Preserved formatting
- **PDFs**: Page-by-page text extraction
- **Word Documents**: Full paragraph extraction
- Attachments linked to specific messages

### AI Capabilities
- Powered by Claude Sonnet 5 via IBM ICA
- Context-aware conversations
- Document analysis and summarization
- Code generation and explanation
- Technical Q&A

## Configuration

### Model Settings
Adjust in `backend/app/config.py`:
- `MAX_TOKENS`: Maximum response length (default: 100,000)
- `MODEL_TIMEOUT`: API timeout in seconds (default: 60)
- `MAX_FILE_SIZE`: Upload limit (default: 50MB)

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
- `PATCH /api/sessions/{id}` - Rename session
- `DELETE /api/sessions/{id}` - Delete session

### Messages
- `POST /api/sessions/{id}/messages` - Send message

### Attachments
- `POST /api/sessions/{id}/attachments` - Upload file
- `GET /api/sessions/{id}/attachments/{id}` - Get attachment

## Notes

- **Internal Use Only**: This tool is built for personal productivity and internal technical work
- **Rate Limits**: IBM ICA API has rate limits; wait 30-60 seconds between requests if you encounter 429 errors
- **Storage**: All data stored locally in the `data/` directory
- **Security**: Keep your `.env` file secure and never commit it to version control

## Troubleshooting

**"Failed to send message" errors:**
- Check your IBM ICA credentials in `.env`
- Verify the endpoint is accessible
- Wait if you're hitting rate limits (HTTP 429)

**Build errors:**
- Ensure Node.js 18+ and Python 3.11+ are installed
- Delete `node_modules` and `package-lock.json`, then reinstall
- Check that all dependencies in `requirements.txt` are installed

**Upload failures:**
- Verify file size is under 50MB
- Ensure file type is supported (.txt, .md, .pdf, .doc, .docx)
- Check the `data/documents` directory exists

## License

Internal use only - Not for public distribution

## Author

Built with ❤️ for personal productivity
