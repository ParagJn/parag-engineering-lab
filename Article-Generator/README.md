# AI Article Generator

Production-style full-stack app that generates a high-quality article from user-provided source URLs using **Google Gemini**, then reviews quality with **Anthropic Claude**.

The app streams live status updates to the UI, supports automatic quality retries, and includes a manual **Apply Claude Suggestions** refinement action.

## Highlights
- Generate one article from a list of URLs.
- Real-time progress via SSE (research, generation, review, retries, completion).
- Claude quality scoring on a 1-10 scale.
- Auto-regeneration loop when score is below threshold.
- Manual refinement button: **Apply Claude Suggestions**.
- Clear user-facing error messages for missing/invalid API keys and connectivity issues.
- Light-theme React UI with Google-style color-accented cards.

## Tech Stack
- Frontend: React + Vite + Tailwind CSS
- Backend: FastAPI (Python)
- LLMs:
  - Google Gemini (research + article generation)
  - Anthropic Claude (quality review + scoring)

## Repository Structure
```text
Article-Generator/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── .env
│   │   └── config.json
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── index.css
│   ├── package.json
│   └── ...
└── README.md
```

## How It Works
### Generation Pipeline
1. User submits one or more URLs.
2. Gemini researches the sources and drafts an article.
3. Claude reviews the article and returns:
   - `score` (1-10)
   - `summary`
   - `improvements[]`
4. If score is below threshold (default `7`), Gemini regenerates using Claude feedback.
5. Retry continues up to configured limit (default `2` retries).

### Manual Refinement
After a result is shown, user can click **Apply Claude Suggestions**:
1. Gemini rewrites using latest Claude suggestions.
2. Claude reviews the refined version again.
3. UI updates in real-time with new score, summary, and article.

## Configuration

### 1) Environment Variables (`backend/app/.env`)
Set your keys in:
`/Users/paragjain/dev-works/parag-engineering-lab/Article-Generator/backend/app/.env`

```env
PORT=8000
FRONTEND_PORT=5173

GOOGLE_API_KEY=your_google_key
ANTHROPIC_API_KEY=your_anthropic_key

APP_CONFIG_PATH=app/config.json
```

Notes:
- Gemini key can be provided as `GOOGLE_API_KEY` (preferred) or `GEMINI_API_KEY`.
- Never commit real API keys to GitHub.

### 2) Runtime Model Config (`backend/app/config.json`)
Current schema:

```json
{
  "llm": {
    "request_timeout_seconds": 90,
    "gemini": {
      "api_base": "https://generativelanguage.googleapis.com/v1beta/models",
      "model": "gemini-3-flash-preview",
      "temperature": 0.7,
      "max_output_tokens": 3000
    },
    "claude": {
      "api_url": "https://api.anthropic.com/v1/messages",
      "model": "claude-sonnet-4-5-20250929",
      "anthropic_version": "2023-06-01",
      "temperature": 0.7,
      "max_tokens": 3000
    }
  }
}
```

Optional quality controls can also be added:

```json
{
  "quality": {
    "min_score": 7,
    "max_retries": 2
  }
}
```

## Local Development

### Backend (shared venv)
```bash
cd /Users/paragjain/dev-works/parag-engineering-lab/Article-Generator/backend
/Users/paragjain/dev-works/myenv/bin/pip install -r requirements.txt
/Users/paragjain/dev-works/myenv/bin/python -m uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd /Users/paragjain/dev-works/parag-engineering-lab/Article-Generator/frontend
npm install
npm run dev
```

Default frontend API base URL: `http://localhost:8000`

## API Reference

### `GET /api/health`
Returns service status and key-configuration booleans.

### `POST /api/generate-stream`
Starts generation + automated quality loop.

Request body:
```json
{
  "urls": [
    "https://example.com/source-1",
    "https://example.com/source-2"
  ]
}
```

### `POST /api/apply-suggestions-stream`
Applies Claude suggestions to current article and re-reviews.

Request body:
```json
{
  "urls": ["https://example.com/source-1"],
  "article": "# Existing markdown article...",
  "review_summary": "Needs clearer structure",
  "improvements": [
    "Improve section transitions",
    "Strengthen fact grounding"
  ]
}
```

### Stream Event Types (SSE)
- `status`
- `review`
- `error`
- `done`

## Error Handling
The UI surfaces actionable errors for:
- Missing `.env` keys
- Invalid Gemini/Claude credentials
- Model/endpoint 404 mismatches
- Backend connectivity issues (`Failed to fetch`)

## Production Notes
- Restrict CORS origins before deploying.
- Add authentication/rate-limits for public deployments.
- Store secrets in a secure secret manager.
- Add structured logging and monitoring.

## License
Add your project license here (for example, MIT).
