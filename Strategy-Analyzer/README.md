# Strategy Analyzer

A multi-agent enterprise strategy document review platform. Upload a PDF, Word document, or PowerPoint presentation and receive structured analysis from four AI agents across two providers — with follow-up chat, Markdown export, and a visual strategy action map.

---

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Feature Summary](#feature-summary)
- [Architecture](#architecture)
- [Multi-Agent Pipeline](#multi-agent-pipeline)
- [Analysis Modes](#analysis-modes)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
  - [Quick Start (both servers)](#quick-start-both-servers)
  - [Backend only](#backend-only)
  - [Frontend only](#frontend-only)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Document Support](#document-support)
- [Visualization](#visualization)
- [Graceful Degradation](#graceful-degradation)
- [Configuration Reference](#configuration-reference)
- [Known Limitations](#known-limitations)

---

## Overview

Strategy Analyzer is designed for executives, architects, and transformation leads who need to quickly review strategy documents and surface actionable insights. Instead of relying on a single AI model, the platform routes every document through a four-agent pipeline — each agent applying a different lens (architecture, cost, validation, synthesis) — and then delivers a unified, evidence-based Markdown report.

The tool is intentionally **opinionated**:
- Analysis stays grounded in the document text — agents are instructed not to invent facts or slide numbers.
- Recommendations focus on three dimensions: **reaching the target state**, **reducing cost**, and **shortening turnaround time**.
- The final report is always Markdown, making it easy to paste into Confluence, export as a DOCX, or commit to a repo.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser (React)                      │
│  Upload document → Select mode → Trigger analysis           │
│  ← Markdown report, PNG visual, follow-up chat              │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP REST  (/api/*)
┌───────────────────────────▼─────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  1. Parse document (pypdf / python-docx / python-pptx)      │
│  2. Run multi-agent pipeline (asyncio.gather)               │
│  3. Synthesize final report                                  │
│  4. Generate PNG visual                                      │
└──────────────┬────────────────────────────┬─────────────────┘
               │                            │
┌──────────────▼──────────┐    ┌────────────▼────────────────┐
│    SAP AI Core          │    │    Azure OpenAI             │
│  ● Claude 4.6 Opus      │    │  ● GPT-5.4 (synthesizer)   │
│    (strategy architect) │    │  ● GPT-5.3 Codex            │
│  ● Gemini 2.5 Pro       │    │    (validator)              │
│    (cost challenger)    │    └─────────────────────────────┘
└─────────────────────────┘
```

---

## Feature Summary

| Feature | Detail |
|---|---|
| Document upload | PDF, DOCX, PPTX — up to 120,000 extracted characters |
| Document preview | In-browser (PDF iframe; extracted text for DOCX/PPTX) |
| Analysis modes | Summarize / Identify Gaps / Give Suggestions |
| Multi-agent review | 4 agents across SAP AI Core + Azure OpenAI |
| Extended reasoning | Claude 4.6 Opus "thinking" mode (adaptive, 12K token budget) |
| Parallel execution | Agents 1–3 run concurrently via `asyncio.gather` |
| Follow-up chat | Conversational Q&A against the generated analysis |
| Markdown export | One-click download of the full analysis report |
| Visual export | 1400×900 PNG "Strategy Action Map" with top 5 recommendations |
| Fallback mode | Returns a local draft template if all providers are unavailable |

---

## Architecture

```
backend/
  app/
    main.py            ← FastAPI routes, CORS, file serving
    analyzer.py        ← Multi-agent orchestration (asyncio)
    llm_clients.py     ← Provider adapters (Azure + SAP AI Core)
    document_parser.py ← PDF / DOCX / PPTX extraction
    visuals.py         ← Pillow-based PNG generation
    config.py          ← Pydantic Settings, env var binding

frontend/
  src/
    App.jsx            ← All React components
    api.js             ← HTTP client functions
    main.jsx           ← Entry point
```

**State model**: Documents are stored in an in-memory Python dict keyed by UUID. There is no database — the application is session-scoped. Data is lost on backend restart.

**API communication**: The Vite dev server proxies all `/api/*` requests to `http://localhost:8000`, so no CORS issues during development and no hardcoded backend URL in the frontend.

---

## Multi-Agent Pipeline

Every analysis request runs through four agents. The first three execute in parallel; the fourth synthesizes their outputs.

```
Document text (≤ 80,000 chars)
        │
        ├──► [1] Claude 4.6 Opus — Strategy Architect
        │         SAP AI Core │ Extended thinking (adaptive, 12K budget)
        │         Max tokens: 9,000 │ Temperature: 0.2
        │         Role: Deep structural and transformation review
        │
        ├──► [2] Gemini 2.5 Pro — Cost Challenger
        │         SAP AI Core │ No thinking mode
        │         Max tokens: 5,500 │ Temperature: 0.2
        │         Role: Cost assumptions, ROI, and reuse opportunities
        │
        ├──► [3] GPT-5.3 Codex — Validator
        │         Azure OpenAI │ Checklist validation
        │         Max tokens: 3,500 │ Temperature: 0.2
        │         Role: Completeness, risk flags, missing evidence
        │
        └──► (above three complete) ──►
             [4] GPT-5.4 — Synthesizer
                  Azure OpenAI │ Markdown output
                  Max tokens: 7,000 │ Temperature: 0.2
                  Role: Combine all three perspectives into final report
```

**System prompt (agents 1–3):**
> You are a senior data architecture, information management, and transformation strategy advisor. Be constructive and precise. Do not invent slide numbers or facts. If slide or page markers exist, cite them. Focus on how to reach the target state, reduce cost, shorten turnaround, and avoid interim technical debt.

**Fallback chain**: If synthesis fails → concatenated agent outputs. If all agents fail → local `_fallback()` template.

---

## Analysis Modes

Select a mode in the UI before triggering analysis. The mode shapes the agent instructions.

| Mode | Behaviour |
|---|---|
| **Summarize** | Preserves document structure, key decisions, risks, economics, and next steps. Best for executive briefings. |
| **Identify Gaps** | Surfaces gaps that materially affect execution — missing data, unresolved dependencies, unstated assumptions. |
| **Give Suggestions** | Recommends practical changes that improve the path from current state to target state. Focuses on cost, turnaround, and reuse. |

Each mode can be combined with a custom free-text prompt for additional focus (e.g., "Pay special attention to cloud cost assumptions").

**Thinking mode toggle**: When enabled, Claude 4.6 Opus uses extended internal reasoning (budget: 12,000 tokens) before producing its output. This improves depth on complex documents at the cost of additional latency.

---

## Project Structure

```
Strategy-Analyzer/
├── README.md
├── start.sh                    ← One-command launcher for both servers
├── backend/
│   ├── requirements.txt
│   ├── .env                    ← Provider credentials (not committed)
│   └── app/
│       ├── __init__.py
│       ├── main.py             ← API routes
│       ├── analyzer.py         ← Orchestration logic
│       ├── llm_clients.py      ← Azure + SAP AI Core clients
│       ├── document_parser.py  ← PDF/DOCX/PPTX extraction
│       ├── visuals.py          ← PNG generation
│       └── config.py           ← Environment configuration
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js          ← Dev proxy to backend
    ├── tailwind.config.js
    ├── postcss.config.js
    └── src/
        ├── App.jsx             ← All UI components
        ├── api.js              ← HTTP client
        ├── main.jsx
        └── index.css
```

---

## Prerequisites

- **Python 3.10+** with a virtual environment
- **Node.js 18+** and npm
- At least one set of provider credentials:
  - SAP AI Core service key (for Claude + Gemini)
  - Azure OpenAI deployment endpoints (for GPT-5.4 and GPT-5.3 Codex)
- The app runs without credentials in fallback mode (useful for UI development)

---

## Setup

### Quick Start (both servers)

```bash
./start.sh
```

This installs backend dependencies, starts uvicorn on port 8000, installs frontend dependencies, and starts Vite on port 5173. Both processes are killed together on Ctrl+C.

> **Note:** `start.sh` references a specific Python virtual environment path. Edit the `PYTHON_ENV` variable at the top of the file to match your local setup before running.

### Backend only

```bash
cd backend

# Create and activate a virtual environment (first time)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp .env.example .env   # then fill in your credentials

# Start the API server
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. Interactive API docs at `http://localhost:8000/docs`.

### Frontend only

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api/*` to the backend automatically.

---

## Environment Variables

Create `backend/.env` by copying `.env.example` and filling in your credentials. All variables are optional — missing providers are skipped gracefully.

### Azure OpenAI — GPT-5.4 Synthesizer

| Variable | Description |
|---|---|
| `AZURE_OPENAI_GPT54_BASE` | Full endpoint URL, e.g. `https://<resource>.openai.azure.com/` |
| `AZURE_OPENAI_GPT54_KEY` | API key |
| `AZURE_OPENAI_GPT54_VERSION` | API version (default: `2025-04-01-preview`) |
| `AZURE_OPENAI_GPT54_DEPLOYMENT` | Deployment name (default: `gpt-5.4-common`) |
| `AZURE_OPENAI_GPT54_RESOURCE_GROUP` | Azure resource group |
| `AZURE_OPENAI_GPT54_REGION` | Azure region |

### Azure OpenAI — GPT-5.3 Codex Validator

| Variable | Description |
|---|---|
| `AZURE_OPENAI_GPT53CODEX_BASE` | Full endpoint URL |
| `AZURE_OPENAI_GPT53CODEX_KEY` | API key |
| `AZURE_OPENAI_GPT53CODEX_VERSION` | API version (default: `2025-04-01-preview`) |
| `AZURE_OPENAI_GPT53CODEX_DEPLOYMENT` | Deployment name (default: `gpt-5.3-codex-common`) |
| `AZURE_OPENAI_GPT53CODEX_RESOURCE_GROUP` | Azure resource group |
| `AZURE_OPENAI_GPT53CODEX_REGION` | Azure region |

### SAP AI Core — Claude + Gemini

| Variable | Description |
|---|---|
| `SAP_CLIENT_ID` | OAuth2 client ID from your SAP AI Core service key |
| `SAP_CLIENT_SECRET` | OAuth2 client secret |
| `SAP_TOKEN_URL` | OAuth2 token endpoint |
| `SAP_API_URL` | SAP AI Core API base URL |
| `SAP_RESOURCE_GROUP` | Resource group name (default: `genius`) |
| `SAP_ANTHROPIC_MODEL` | Model ID (default: `anthropic--claude-4.6-opus`) |
| `SAP_GEMINI_MODEL` | Model ID (default: `gemini-2.5-pro`) |
| `SAP_THINKING_MODE` | `adaptive`, `enabled`, or `disabled` (default: `adaptive`) |
| `SAP_THINKING_BUDGET_TOKENS` | Thinking token budget (default: `12000`) |

### Other

| Variable | Description |
|---|---|
| `UPLOAD_DIR` | Directory for uploaded files (default: `./uploads`) |

---

## API Reference

All endpoints are prefixed with `/api`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check — returns `{"status": "ok"}` |
| `GET` | `/api/sap/models` | Lists available foundation models from SAP AI Core |
| `POST` | `/api/upload` | Upload a document file (multipart/form-data, field: `file`) |
| `GET` | `/api/file/{document_id}` | Retrieve a previously uploaded file |
| `POST` | `/api/analyze` | Run multi-agent analysis |
| `POST` | `/api/chat` | Ask a follow-up question about the analysis |
| `POST` | `/api/visual` | Generate a PNG strategy action map |
| `GET` | `/api/visuals/{filename}` | Serve a generated PNG file |

### POST /api/analyze

```json
{
  "document_id": "string",
  "mode": "summarize | identify_gaps | give_suggestions",
  "prompt": "optional additional instructions",
  "thinking_mode": true
}
```

Returns:

```json
{
  "analysis": "Markdown string",
  "agents": [
    { "agent": "Strategy Architect", "content": "...", "ok": true },
    { "agent": "Cost Challenger",    "content": "...", "ok": true },
    { "agent": "Codex Validator",    "content": "...", "ok": true },
    { "agent": "Synthesizer",        "content": "...", "ok": true }
  ],
  "warning": "optional string if fallback was used"
}
```

### POST /api/chat

```json
{
  "document_id": "string",
  "analysis": "the full analysis Markdown",
  "question": "your follow-up question",
  "history": [
    { "role": "user",      "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

### POST /api/visual

```json
{
  "document_id": "string",
  "analysis": "the full analysis Markdown"
}
```

Returns: `{ "url": "/api/visuals/<filename>.png" }`

---

## Document Support

| Format | Parser | Notes |
|---|---|---|
| PDF (`.pdf`) | pypdf | Text layer only. Scanned/image PDFs will produce empty or sparse output. |
| Word (`.docx`) | python-docx | Extracts paragraphs and tables. Tables rendered as pipe-delimited rows. |
| PowerPoint (`.pptx`) | python-pptx | Extracts all text shapes per slide. Slide title inferred from first line of slide text. |

**Extraction limits:**
- Up to **120,000 characters** are stored per document.
- Up to **80,000 characters** are passed to the analysis pipeline (to stay within model token budgets).
- The frontend preview shows up to the first **40 pages or slides**.

---

## Visualization

After analysis, clicking **Generate Visual** produces a branded 1400×900 PNG image:

- **Header**: "Strategy Action Map" title on dark slate background
- **Three-column framework**: Objective (blue) / Cost (green) / Turnaround (purple)
- **Priority recommendations**: Top 5 bullet points extracted from the analysis Markdown
- **Design**: Rounded cards, Inter/Arial font, slate color palette

The image is saved to `backend/uploads/visuals/` and served via `GET /api/visuals/<filename>`. It can be downloaded directly from the UI.

---

## Graceful Degradation

The platform is designed to remain usable when provider credentials are missing or endpoints are unreachable:

1. **Thinking mode**: If Claude's endpoint rejects the `thinking` parameter, the request is automatically retried without it.
2. **Agent failure**: If any individual agent fails, its `ok: false` result is recorded but the pipeline continues with the remaining agents.
3. **Synthesis failure**: If GPT-5.4 is unavailable, the concatenated outputs from the other three agents are returned directly.
4. **All agents unavailable**: A local `_fallback()` template is returned with the document excerpt and applied prompt, plus a warning message in the UI.

This means you can run the frontend with no credentials at all and still verify the UI, upload flow, and document preview.

---

## Configuration Reference

Key defaults (all overridable via `.env`):

| Setting | Default |
|---|---|
| Backend port | `8000` |
| Frontend port | `5173` |
| Azure API version | `2025-04-01-preview` |
| GPT-5.4 deployment | `gpt-5.4-common` |
| GPT-5.3 Codex deployment | `gpt-5.3-codex-common` |
| SAP Anthropic model | `anthropic--claude-4.6-opus` |
| SAP Gemini model | `gemini-2.5-pro` |
| Thinking mode | `adaptive` |
| Thinking token budget | `12,000` |
| LLM temperature | `0.2` |
| Max document chars (storage) | `120,000` |
| Max document chars (analysis) | `80,000` |
| SAP request timeout | `180s` |
| Azure request timeout | `120s` |

---

## Known Limitations

- **No persistence**: Documents and analyses are held in memory and lost on backend restart. There is no database.
- **No authentication**: The API has no access controls. Do not expose it on a public network.
- **No streaming**: LLM responses are returned in full after generation. Long analyses (7K+ tokens) can take 30–60 seconds.
- **Scanned PDFs**: Image-only PDFs will not extract usable text. OCR is not included.
- **CORS**: Configured for `localhost` only. Change `allow_origins` in `main.py` for other deployment targets.
- **No rate limiting**: Repeated calls to `/api/analyze` will trigger billable LLM requests each time.

