# Profile Generator V2

Profile Generator V2 rebuilds CVs from user-provided documents and links using a true two-stage LLM pipeline:
- Gemini (via `google.genai`): research + evidence-grounded profile extraction
- Anthropic: completely rewritten professional CV generation

Outputs:
- Professional responsive HTML CV
- Markdown CV
- Structured JSON profile
- ATS optimization report
- Research summary from Gemini

## Core Goals
- Produce high-quality, recruiter-ready profiles from fragmented source material.
- Improve ATS discoverability using role-aligned keyword strategy.
- Keep claims grounded in user-provided evidence.

## Stack
- Backend: FastAPI (Python), async job pipeline
- LLMs: Google Gen AI SDK (`google.genai`) + Anthropic Claude
- Frontend: React + Tailwind CSS (Vite), mobile/tablet/desktop responsive

## Project Structure

```text
Profile-Generator-V2/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── state.py
│   │   ├── models/schemas.py
│   │   ├── routers/{upload.py, generate.py}
│   │   └── services/
│   │       ├── parser.py
│   │       ├── link_fetcher.py
│   │       ├── llm_cv_pipeline.py
│   │       ├── ats_optimizer.py
│   │       └── renderer.py
│   └── requirements.txt
├── frontend/
├── uploads/
├── output/
├── install.sh
└── start.sh
```

## Environment Variables
Create `.env` in project root (`Profile-Generator-V2/.env`) with:

```bash
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=...
# Optional
OPENAI_API_KEY=...
```

`GEMINI_API_KEY` and `ANTHROPIC_API_KEY` are required for CV generation in V2.

## Setup

Uses your requested venv:
- `/Users/paragjain/dev-works/myenv`

Install:

```bash
cd /Users/paragjain/dev-works/parag-engineering-lab/Profile-Generator-V2
chmod +x install.sh start.sh
./install.sh
```

Run:

```bash
./start.sh
```

Frontend:
- http://localhost:5173

Backend:
- http://localhost:8000

## API Endpoints
- `POST /api/upload` upload source files, returns `session_id`
- `POST /api/generate` start generation job
- `GET /api/status/{job_id}` poll job status
- `GET /api/result/{job_id}` retrieve generated outputs + ATS report
- `GET /api/download/{job_id}/{kind}` download artifact:
  - `html`, `markdown`, `json`, `txt`, `research`
- `GET /api/health` health check

## Generation Pipeline
1. Parse uploaded files and fetch link text.
2. Gemini (via `google.genai`) performs research and builds a structured evidence-grounded profile model.
3. Anthropic generates a completely new CV markdown from evidence + Gemini strategy.
4. ATS analysis computes keyword match, misses, and improvement tips.
5. HTML renderer produces professional responsive CV view.

## Queue/Hang Fix
- Gemini and Anthropic SDK calls run in worker threads (`asyncio.to_thread`) to prevent blocking FastAPI's event loop.
- This avoids jobs appearing stuck in queued/researching due to synchronous SDK calls.
