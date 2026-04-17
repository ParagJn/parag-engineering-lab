# Morning Edition

AI-curated daily tech magazine generator. Select from 10 top tech news sources (or blend up to 5), and get a beautifully rendered, self-contained HTML magazine with editorial-grade content, 10 distinct visual spread styles, and full SEO markup — ready to upload to the web.

![React](https://img.shields.io/badge/React-19-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green) ![Claude](https://img.shields.io/badge/Claude-Sonnet%204-purple) ![Gemini](https://img.shields.io/badge/Gemini-2.0%20Flash-orange)

## How It Works

```
RSS Feeds (10 sources)
    ↓
Gemini 2.0 Flash — enriches, categorizes, picks top 10 stories
    ↓
Claude Sonnet 4 — writes editorial headlines, body, pull quotes, assigns spread styles
    ↓
Self-contained HTML magazine with TOC, SEO, JSON-LD, 10 visual spreads
```

## Features

- **Multi-Source Blending** — Pick 1–5 sources to generate a cross-source "state of tech" digest
- **10 Visual Spread Styles** — hero, midnight, rose alert, terminal, academic, big stat, blueprint, neon, editorial, sunset
- **Table of Contents** — Clickable anchor links to each story with smooth scroll navigation
- **Back-to-Top Button** — Floating button appears on scroll
- **SEO-Ready HTML** — meta description, keywords, Open Graph, Twitter Cards, JSON-LD structured data
- **Archive System** — Every generated magazine is saved to disk with metadata; browse, reload, delete, or regenerate from the sidebar
- **Delete & Regenerate** — Available in both the archive sidebar and the main action bar
- **PDF Export** — Chromium-rendered PDF with pixel-perfect styling and clickable hyperlinks (via Playwright)
- **Email Newsletter** — Send a styled HTML digest with the full magazine PDF attached via SMTP

## News Sources

| Source | Type |
|---|---|
| Hacker News | RSS |
| TechCrunch | RSS |
| The Verge | RSS |
| Ars Technica | RSS |
| Wired | RSS |
| The New Stack | RSS |
| BleepingComputer | RSS |
| MIT Technology Review | RSS |
| VentureBeat | RSS |
| Dark Reading | RSS |

## Project Structure

```
├── backend/
│   ├── main.py          # FastAPI app, API endpoints, archive management
│   ├── sources.py       # 10 news source configurations (RSS feeds)
│   ├── fetcher.py       # RSS fetching (httpx + feedparser) + Gemini enrichment
│   ├── curator.py       # Anthropic Claude editorial curation
│   ├── magazine.py      # HTML magazine renderer (spreads, TOC, SEO, JSON-LD)
│   ├── pdf_generator.py # PDF export via Playwright (headless Chromium)
│   ├── emailer.py       # Email delivery with PDF attachment (SMTP)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx      # Main React app (multi-select, sidebar, iframe preview)
│   │   ├── App.css
│   │   ├── index.css    # Tailwind v4 + fonts
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js   # Vite + Tailwind + API proxy
├── Archive/             # Generated magazines (HTML + JSON metadata)
├── .env                 # API keys (not committed)
└── .gitignore
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Anthropic API key
- Google Gemini API key

### 1. Clone & configure environment

```bash
git clone <repo-url>
cd Daily-Articles-Pages
```

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AI...

# Optional: Email delivery
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_NAME=Morning Edition
```

> **Gmail users**: Use an [App Password](https://myaccount.google.com/apppasswords) for `SMTP_PASSWORD`.

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/sources` | List available news sources |
| `POST` | `/api/generate` | Generate magazine from `{ source_ids: [...] }` |
| `GET` | `/api/archive` | List all archived magazines |
| `GET` | `/api/archive/{filename}` | Serve archived HTML |
| `DELETE` | `/api/archive/{filename}` | Delete a specific archive entry |
| `DELETE` | `/api/archive` | Clear all archives |
| `GET` | `/api/archive/{filename}/pdf` | Download magazine as PDF |
| `POST` | `/api/send-email` | Send magazine email `{ filename, to_emails: [...] }` |

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite 8, Tailwind CSS 4 |
| Backend | FastAPI, Uvicorn, Pydantic |
| AI — Enrichment | Google Gemini 2.0 Flash |
| AI — Editorial | Anthropic Claude Sonnet 4 |
| RSS Parsing | feedparser, httpx |
| PDF Generation | Playwright (headless Chromium) |
| Email | smtplib (SMTP/TLS) |
| Fonts | Fraunces, Inter, JetBrains Mono |
