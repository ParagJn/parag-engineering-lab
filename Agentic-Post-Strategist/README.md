# Agentic Social Studio

Use the power of agentic AI with multiple LLMs to generate comprehensive social media strategies, content calendars, and engagement plans tailored to your niche and audience.

## Features

- 8 built-in social media operations:
  - Niche Intelligence & Audience Mapping
  - Market Positioning & Brand Strategy
  - Content Pillar Architecture
  - 30-Day Content Calendar Generator
  - Step Validation
  - Viral Hook Formula Creator
  - Engagement & Community Builder
  - Analytics Interpreter & Optimizer
- Parallel model execution:
  - Gemini agent
  - Claude agent
- Unified synthesized output panel for execution-ready recommendations.

## Setup

1. Install frontend dependencies:

```bash
npm install
```

2. Install backend dependencies into the shared Python environment:

```bash
/Users/paragjain/dev-works/myenv/bin/pip install -r requirements.txt
```

3. Configure environment:

```bash
cp .env.example .env
```

Fill in `GOOGLE_API_KEY` and `ANTHROPIC_API_KEY`.

4. Configure non-secret runtime settings in:

```bash
app/config.json
```

This JSON file controls:
- server port default
- Gemini model, API base URL, temperature, max output tokens
- Claude model, API URL, anthropic version, temperature, max tokens
- shared request timeout

## Run

- Full app (Vite + FastAPI):

```bash
npm run dev
```

- Or backend only:

```bash
/Users/paragjain/dev-works/myenv/bin/uvicorn app.main:app --reload --port 8787
```

- Frontend only:

```bash
npm run dev:client
```

## API Endpoints

- `GET /api/health`
- `GET /api/operations`
- `POST /api/generate`

### Sample `POST /api/generate` body

```json
{
  "operation": "calendar_30_day",
  "niche": "AI productivity coaching",
  "platform": "LinkedIn",
  "audience": "Founders and startup operators",
  "metrics": "CTR 1.8%, avg engagement 3.2%",
  "extra_context": "Tone should be direct and premium"
}
```
