# Skills Generator — Project Context

## Summary

This project is a full-stack AI skill generator that converts a user's thought/idea into a fully structured, production-ready skill definition (markdown file) compatible with **Anthropic (Claude Sonnet)**, **Google Gemini (2.0 Flash)**, or **ChatGPT (GPT-4o)**.

## Tech Stack

- **Backend**: Python + FastAPI (`backend/main.py`), served via Uvicorn on port 8000
- **Frontend**: Vanilla HTML/JS + Tailwind CSS (CDN), served as static files by FastAPI
- **LLM SDKs**: `openai`, `anthropic`, `google-generativeai` (all latest versions)
- **Python venv**: `/Users/paragjain/dev-works/myenv` (shared venv, not project-local)

## How to Run

```bash
cd /Users/paragjain/dev-works/parag-engineering-lab/Skills-Generator
source /Users/paragjain/dev-works/myenv/bin/activate
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000

## Project Structure

```
Skills-Generator/
├── backend/
│   ├── main.py              # FastAPI app — all API routes, LLM calls, file I/O
│   └── requirements.txt     # Python deps (>=  style, not pinned)
├── frontend/
│   ├── package.json          # Node/Tailwind config
│   ├── tailwind.config.js    # Google-themed colors (blue/red/yellow/green)
│   ├── postcss.config.js
│   ├── src/input.css
│   └── public/
│       ├── index.html        # Single-page responsive UI
│       └── app.js            # Client-side JS (all state, API calls, rendering)
├── skills/                   # Output folder — generated .md skill files
│   └── .archive/             # Archived skills moved here
├── .env                      # API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY + others)
├── .gitignore
├── README.md
└── context.md                # This file
```

## Key Features Implemented

1. **Skill generation** — User picks a platform (radio cards), types a thought, clicks Generate. Backend calls the selected LLM with a structured prompt, saves the output as `skills/<skill-name>.md`, stores metadata in `skills/.metadata.json`.
2. **Usage guide** — After generating a skill, a second LLM call produces beginner-friendly "How to Use" notes (displayed in a yellow-bordered card).
3. **Test skill** — "Test Skill" button sends the skill content to the same LLM to generate and run a test case, displayed in a green-bordered card.
4. **Sidebar** — Left panel lists all generated skills for quick re-access. Responsive: hamburger menu on mobile/tablet, always visible on desktop.
5. **Actions** — Regenerate (refresh icon), Archive (archive icon), Delete (trash icon), Download (download icon) — all wired to backend endpoints.
6. **Full-width layout** — Content area uses full available width with responsive padding (`px-4` → `px-16`).
7. **Google-themed UI** — Card borders use Google colors (red=Anthropic, blue=Gemini, green=ChatGPT). Material Symbols glyphs throughout. Inter font.

## API Endpoints (backend/main.py)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/generate` | Generate skill + usage notes |
| GET | `/api/skills` | List all non-archived skills |
| GET | `/api/skills/{id}` | Get single skill with content |
| DELETE | `/api/skills/{id}` | Delete skill permanently |
| POST | `/api/skills/{id}/archive` | Move to archive |
| POST | `/api/skills/{id}/regenerate` | Regenerate from original thought |
| POST | `/api/skills/{id}/test` | Generate & run test case |
| GET | `/api/skills/{id}/download` | Download .md file |
| GET | `/` | Serve frontend |

## .env Keys Used

- `OPENAI_API_KEY` — for ChatGPT/GPT-4o
- `ANTHROPIC_API_KEY` — for Claude Sonnet
- `GEMINI_API_KEY` — for Gemini 2.0 Flash

(The .env file also contains Azure OpenAI, LLAMA, X AI, and other keys not currently used by this app.)

## Design Decisions

- Tailwind is loaded via CDN (`cdn.tailwindcss.com`) for simplicity — no build step needed for dev. The npm/Tailwind setup exists for production builds.
- `marked.js` (CDN) renders markdown in the browser.
- Metadata (skill IDs, names, platforms, thoughts, usage notes, timestamps) stored in `skills/.metadata.json`.
- The `google-generativeai` package shows a deprecation warning (switch to `google.genai` in future).
- Frontend is purely vanilla JS — no framework.

## Pending / Future Improvements

- Switch from `google.generativeai` to `google.genai` (new SDK)
- Add favicon
- Add search/filter in sidebar
- Add skill editing capability
- Add export-all / batch operations
