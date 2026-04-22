# Profile Generator

An AI-powered tool that turns your resume documents and public profile links into a polished **HTML CV**, a **print-ready PDF**, and a **LinkedIn copy-paste helper** — all in one click.

---

## How it works

```
Upload docs / add links
        ↓
Gemini 2.5 Pro  →  Structured JSON profile
        ↓
Claude Opus     →  Animated HTML CV  +  LinkedIn Helper HTML
        ↓
Playwright      →  Print-perfect PDF
```

1. **Upload** your resume (PDF, DOCX, or HTML) and/or paste public profile links (GitHub, LinkedIn, portfolio).
2. **Gemini 2.5 Pro** extracts a rich structured JSON with experience, projects, skills, certifications, and more.
3. **Claude Opus** generates a beautiful single-file HTML resume and a LinkedIn profile copy-paste tool.
4. **Playwright** renders the HTML to a pixel-perfect PDF.
5. Once generated, use the **Request Changes** prompt box to iteratively refine any aspect — all three files are regenerated with your context preserved.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 · FastAPI · Uvicorn |
| AI Stage 1 | Google Gemini 2.5 Pro (`google-generativeai`) |
| AI Stage 2 | Anthropic Claude Opus (`anthropic`) |
| PDF Export | Playwright (headless Chromium) |
| Document Parsing | pdfplumber · python-docx · BeautifulSoup4 |
| Frontend | React 18 · Vite · Tailwind CSS |
| API Enrichment | GitHub REST API |

---

## Project Structure

```
Profile-Generator/
├── backend/
│   ├── main.py                 # FastAPI app entry point
│   ├── requirements.txt
│   ├── models/
│   │   └── schemas.py
│   ├── routers/
│   │   ├── upload.py           # File upload endpoint
│   │   └── generate.py         # Generation + refinement pipeline
│   └── services/
│       ├── ai_service.py       # Gemini extraction + Claude generation/refinement
│       ├── parser.py           # PDF / DOCX / HTML text extraction
│       └── pdf_export.py       # Playwright HTML → PDF
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # Main app + refine prompt logic
│   │   ├── components/
│   │   │   ├── Header.jsx
│   │   │   ├── UploadZone.jsx
│   │   │   ├── LinksInput.jsx
│   │   │   ├── OutputPanel.jsx # CV / LinkedIn / Downloads tabs
│   │   │   └── ProgressOverlay.jsx
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
├── uploads/                    # Temporary upload storage (gitignored)
├── output/                     # Generated files per job (gitignored)
├── .env.example                # Environment variable template
├── install.sh                  # One-shot dependency installer
└── start.sh                    # Start backend + frontend together
```

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Playwright browsers](https://playwright.dev/python/docs/intro): `playwright install chromium`

### 1. Clone and configure

```bash
git clone https://github.com/ParagJn/parag-engineering-lab.git
cd parag-engineering-lab/Profile-Generator

cp .env.example .env
# Edit .env and fill in your API keys
```

### 2. Install dependencies

```bash
chmod +x install.sh && ./install.sh
```

Or manually:

```bash
# Backend
cd backend
pip install -r requirements.txt
playwright install chromium

# Frontend
cd ../frontend
npm install
npm run build
```

### 3. Run

```bash
chmod +x start.sh && ./start.sh
```

Then open [http://localhost:5173](http://localhost:5173).

---

## Environment Variables

Copy `.env.example` to `.env` and set the following:

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | ✅ | Google AI Studio key — [get one here](https://aistudio.google.com/apikey) |
| `ANTHROPIC_API_KEY` | ✅ | Anthropic key — [console.anthropic.com](https://console.anthropic.com) |
| `GITHUB_TOKEN` | Optional | Enriches profiles with public repo data |

---

## Key Features

- **Two-stage AI pipeline** — Gemini for structured extraction, Claude for creative HTML generation
- **Iterative refinement** — After generation, ask for changes in plain English; all three output files are regenerated with full context
- **Single-file HTML resume** — Dark gradient header, Font Awesome icons, scroll animations, print CSS
- **LinkedIn copy-paste helper** — Character counters per section, one-click copy buttons
- **PDF export** — Playwright renders with full CSS fidelity including gradients and icons
- **Light neutral UI** — Clean white/gray interface with real-time progress overlay

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload documents, returns `session_id` |
| `POST` | `/api/generate` | Start generation job, returns `job_id` |
| `POST` | `/api/refine` | Refine existing outputs with instructions |
| `GET` | `/api/status/{job_id}` | Poll job progress |
| `GET` | `/api/result/{job_id}` | Fetch completed HTML outputs |
| `GET` | `/api/download/{job_id}/pdf` | Download PDF |
| `GET` | `/api/download/{job_id}/cv-html` | Download HTML resume |
| `GET` | `/api/download/{job_id}/linkedin-html` | Download LinkedIn helper |
| `GET` | `/api/health` | Health check |
