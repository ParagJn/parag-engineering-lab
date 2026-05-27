# Profile Generator V2

Profile Generator V2 is a full-stack ATS-focused CV generation app that transforms uploaded documents and public links into:
- A professional responsive HTML CV
- A clean Markdown CV
- A structured JSON profile for downstream systems/agentic indexing
- An ATS optimization report (keywords used, missing, and improvement actions)

## Core Goals
- Produce highly professional profiles from fragmented inputs.
- Maximize recruiter-system discoverability with contextual keywords.
- Keep outputs accurate by grounding sections in extracted source evidence.

## Stack
- Backend: FastAPI (Python), async pipeline, file/link ingestion, ATS optimization
- Frontend: React + Tailwind CSS (Vite), responsive from mobile to desktop

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
│   │       ├── profile_builder.py
│   │       ├── ats_optimizer.py
│   │       └── renderer.py
│   └── requirements.txt
├── frontend/
│   ├── package.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       └── index.css
├── uploads/
├── output/
├── install.sh
└── start.sh
```

## Setup

Use your specified virtual environment:
- `/Users/paragjain/dev-works/myenv`

### Install

```bash
cd /Users/paragjain/dev-works/parag-engineering-lab/Profile-Generator-V2
chmod +x install.sh start.sh
./install.sh
```

### Run

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
- `GET /api/download/{job_id}/{kind}` download artifact (`html`, `markdown`, `json`, `txt`)
- `GET /api/health` health check

## Accuracy Notes
- V2 uses deterministic extraction and evidence-aware summarization by default.
- If `OPENAI_API_KEY` is set, the backend can apply optional LLM-assisted section refinement for stronger phrasing while preserving factual anchors.
