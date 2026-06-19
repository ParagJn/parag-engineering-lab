# Interview Coach — AI-Powered Interview Preparation Platform

Prepare for job interviews with a multi-agent AI coaching platform powered by **GPT-4**, **Gemini**, and **Claude**. Upload your job description, select an interview type, answer questions posed by AI agents, and receive consolidated feedback with scores from all three models.

---

## Features

- **Multi-Agent Question Panel** — Three independent AI agents (OpenAI GPT-4, Google Gemini, Anthropic Claude) collaboratively generate the top 6 interview questions tailored to your role, company, and interview type.
- **Company-Aware Questions** — The platform analyses the company's profile and adjusts question depth accordingly (e.g., AI-heavy questions for AI-native companies, process/management focus for captive-style organisations).
- **Four Interview Types**
  - Technical
  - Management / Leadership
  - Behavioural
  - Salary Negotiation
- **Real-Time Evaluation** — After each answer, all three agents independently score the response (1–10) and provide detailed feedback.
- **Consolidated Feedback Report** — A synthesised report combining all three agents' evaluations at the end of the session.
- **Session Management** — Sessions are persisted as JSON files on the local filesystem, allowing you to resume at any time.
- **Progress Dashboard** — Track scores and performance trends across multiple sessions using interactive charts (Recharts).
- **Mobile-Friendly UI** — Fully responsive React interface styled with Tailwind CSS.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS, React Router, Recharts, Axios |
| Backend | Python, FastAPI, Uvicorn, httpx |
| AI Models | OpenAI GPT-4 (via SAP AI Core), Google Gemini (via SAP AI Core), Anthropic Claude (via SAP AI Core) |
| Session Storage | Local filesystem (JSON files) |

---

## Project Structure

```
Interview-Coach/
├── start.sh                  # One-command setup & launch script
├── App-Details.md            # Original app specification
├── sessions/                 # Persisted interview session JSON files
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py           # FastAPI app entry point
│       ├── config.py         # Configuration loader
│       ├── dependencies.py   # Dependency injection
│       ├── models/           # Pydantic data models
│       ├── routes/
│       │   ├── interview.py  # Question generation & answer evaluation endpoints
│       │   ├── sessions.py   # Session CRUD endpoints
│       │   └── dashboard.py  # Progress analytics endpoints
│       ├── services/         # AI agent orchestration logic
│       └── utils/            # Shared utilities
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    └── src/
        ├── App.jsx
        ├── main.jsx
        ├── styles.css
        ├── api/              # Axios API client modules
        ├── components/
        │   ├── common/
        │   ├── setup/
        │   ├── interview/
        │   └── dashboard/
        └── pages/
            ├── SetupPage.jsx      # Job description & profile input
            ├── InterviewPage.jsx  # Live interview session
            ├── ReportPage.jsx     # Post-interview feedback report
            └── DashboardPage.jsx  # Progress tracking dashboard
```

---

## Setup & Run

### Prerequisites

- Python 3.10+ with a virtual environment at `/Users/<you>/dev-works/myenv`
- Node.js 18+
- SAP AI Core credentials (or equivalent OpenAI / Gemini / Anthropic keys)

### Quick Start (recommended)

```bash
chmod +x start.sh
./start.sh
```

The script will:
1. Create the `sessions/` directory if it does not exist
2. Activate (or create) the Python virtual environment
3. Install / verify all backend Python dependencies
4. Install / verify all frontend Node.js dependencies
5. Start the FastAPI backend server
6. Start the Vite dev server

### Manual Start

**Backend**

```bash
source /Users/paragjain/dev-works/myenv/bin/activate
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173` and the backend API at `http://localhost:8000`.

---

## Configuration

All API keys and model settings are stored in `backend/config.json`. Copy and update:

```json
{
  "SAP_CLIENT_ID": "<your-client-id>",
  "SAP_CLIENT_SECRET": "<your-client-secret>",
  "SAP_TOKEN_URL": "<oauth-token-url>",
  "SAP_API_URL": "<api-url>",
  "SAP_RESOURCE_GROUP": "genius",
  "SAP_ANTHROPIC_MODEL": "anthropic--claude-4.6-opus",
  "SAP_GEMINI_MODEL": "gemini-2.5-pro",
  "SAP_THINKING_MODE": "adaptive",
  "SAP_THINKING_BUDGET_TOKENS": 12000
}
```

> **Security note:** Never commit `config.json` with real credentials to version control. Add it to `.gitignore`.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/interview/setup` | Submit job description & profile |
| `POST` | `/api/interview/questions` | Generate 6 questions via all three agents |
| `POST` | `/api/interview/evaluate` | Evaluate a user answer (returns scores + feedback from all agents) |
| `GET` | `/api/sessions` | List all saved sessions |
| `GET` | `/api/sessions/{id}` | Get a specific session |
| `DELETE` | `/api/sessions/{id}` | Delete a session |
| `GET` | `/api/dashboard/stats` | Aggregate performance statistics |

---

## Interview Flow

```
1. Setup Page
   └─ Enter company name, job title, job description, years of experience

2. Select Interview Type
   └─ Technical | Management | Behavioural | Salary Negotiation

3. Interview Session (6 Questions)
   └─ Any of the 3 AI agents asks the next question
   └─ User types their answer
   └─ All 3 agents evaluate and score (1–10)

4. Report Page
   └─ Consolidated feedback from all three agents
   └─ Per-question breakdown with scores

5. Dashboard
   └─ Historical session tracking and performance charts
```

---

## Session Storage

Sessions are stored locally under `sessions/` as JSON files named by UUID (e.g., `sessions/924fc076-10dc-406e-8e62-27ac6794f5a3.json`). Each file contains:

- Job setup metadata (company, title, description, experience)
- Interview type
- All questions and user answers
- Per-agent scores and feedback for each answer
- Final consolidated report
- Timestamps

---

## License

This project is part of the [parag-engineering-lab](https://github.com/ParagJn/parag-engineering-lab) mono-repo.
