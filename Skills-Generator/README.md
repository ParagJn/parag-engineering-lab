# Skills Generator

An AI-powered skill generator. It turns an idea into a complete, installable **Claude Code skill bundle**: `SKILL.md` with spec-compliant frontmatter, reference docs, executable helper scripts, templates, and evals. It also produces Gemini bundles and ChatGPT instruction files. All generation runs through **IBM ICA**, which is the only model provider.

![Vite](https://img.shields.io/badge/Vite-Frontend-646CFF?logo=vite&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-UI-06B6D4?logo=tailwindcss&logoColor=white)

---

## Features

- **Full skill bundles (Claude Code first)**: each skill is a folder containing `SKILL.md` (a concise workflow under 500 lines), `reference/*.md` loaded on demand, `scripts/*` helpers run through `${CLAUDE_SKILL_DIR}`, `templates/`, `examples.md`, and `evals/evals.json`.
- **Generation options**: invocation (auto / slash-command only / background knowledge), scripts (auto / yes / no), and script language (Python / Bash / Node).
- **Staged, streamed pipeline**: Design → Write files → Validate → Repair → Usage guide → Save. Progress streams live over SSE.
- **Static validation**: frontmatter rules, broken links, unreferenced files, and script syntax (`ast.parse`, `bash -n`, `node --check`). Generated scripts are **never executed**. When validation finds errors, the pipeline sends them back to the model to repair (up to `MAX_REPAIR_ROUNDS`).
- **Evals**: runs each scenario in `evals/evals.json` against the skill, then grades every expected behaviour ✓/✗ with a reason and suggestions.
- **Install to `~/.claude/skills`**: one click makes the skill available in every Claude Code project. You're asked before a folder the app didn't create is overwritten.
- **Project sync**: Anthropic bundles are mirrored to `.claude/skills/` and Gemini bundles to `.gemini/skills/`.
- **File-level editing**: view any file with syntax highlighting, and edit or delete it. Every change is re-validated, and the installed copy is kept in sync.
- **Upgrade legacy skills**: older single-file skills show an "Upgrade to full bundle" button, which regenerates them under the same id.
- **Download** a `.zip` of the whole folder. Scripts keep their executable bit.

## Tech Stack

| Layer    | Technology                                                  |
|----------|-------------------------------------------------------------|
| Backend  | Python, FastAPI, Uvicorn (API only, `127.0.0.1:8000`)        |
| Frontend | Vite, Tailwind CSS, vanilla JS, marked + DOMPurify + highlight.js (`localhost:5173`) |
| LLM      | IBM ICA chat completions                                    |

## Project Structure

```
Skills-Generator/
├── .env                      # IBM ICA credentials (not committed) — see .env.example
├── .env.example
├── start.sh                  # One-command startup (backend + frontend)
├── backend/
│   ├── main.py               # FastAPI app — /api routes
│   ├── config.py             # Settings, loaded from the root .env
│   ├── model_service.py      # IBM ICA model service (platform -> model mapping)
│   ├── ibm_ica_client.py     # IBM ICA chat completions client
│   ├── generator.py          # Generation + eval pipelines (async event streams)
│   ├── prompts.py            # Authoring guide, blueprint/bundle/repair/eval prompts
│   ├── skill_spec.py         # Spec rules: name/description limits, allowed fields and paths
│   ├── bundle.py             # <<<FILE>>> parsing, frontmatter helpers
│   ├── validator.py          # Deterministic static checks (never runs scripts)
│   ├── skill_store.py        # Multi-file storage, metadata, sync, install, zip
│   └── requirements.txt
├── frontend/
│   ├── index.html            # Single-page UI
│   ├── src/main.js           # Views, sidebar, actions
│   ├── src/api.js            # fetch + POST SSE stream reader
│   ├── src/bundle-view.js    # File tree, viewer/editor, validation panel
│   ├── src/render.js         # Markdown + highlight.js helpers
│   ├── src/style.css         # Tailwind + prose styles
│   ├── vite.config.mjs       # Port 5173, /api proxy -> backend
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── package.json
├── skills/                   # Generated bundles (<name>/...) + .metadata.json
├── .claude/skills/           # Synced Anthropic skills
└── .gemini/skills/           # Synced Gemini skills
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- An IBM ICA endpoint and API key

## Setup

### 1. Configure credentials

Copy `.env.example` to `.env` in the project root and fill in your IBM ICA values:

```env
IBM_ICA_API_KEY=<your-ica-key>
IBM_ICA_ENDPOINT=https://<your-ica-host>
IBM_ICA_MODEL_ID=claude-opus-5-5          # Anthropic + ChatGPT skills
IBM_ICA_GEMINI_MODEL_ID=gemini-3.7-flash  # Gemini skills

# Optional
# IBM_ICA_INSECURE_TLS=false   # true only for local testing
# MODEL_TIMEOUT=300                # seconds per model call
# MAX_TOKENS=8000                  # short calls (usage notes, evals)
# GENERATION_MAX_TOKENS=16000      # writing a whole bundle
# MAX_REPAIR_ROUNDS=2
# CLAUDE_PERSONAL_SKILLS_DIR=~/.claude/skills
```

The root `.env` is the only config file. Restart the app after changing it.

### 2. Start

```bash
./start.sh
```

This script:
1. checks the project structure, then activates the Python venv and installs backend dependencies if any are missing,
2. checks that the IBM ICA keys are set in `.env` and stops if they aren't,
3. runs `npm install` if needed, then runs `npm run build` to verify the frontend compiles,
4. frees ports 8000 and 5173 by stopping whatever is using them,
5. starts the backend at **http://127.0.0.1:8000** and waits until `/api/health` responds,
6. starts the Vite frontend at **http://localhost:5173**, which opens in your browser,
7. keeps watching both processes and prints the last log lines if either one dies.

Logs and PID files go to `logs/` (`tail -f logs/backend.log`). Press **Ctrl+C** to stop everything.

### Manual start (alternative)

```bash
# Terminal 1 — backend
pip install -r backend/requirements.txt
uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

# Terminal 2 — frontend
cd frontend && npm install && npm run dev
```

The frontend proxies every `/api` request to the backend. Interactive API docs are at http://127.0.0.1:8000/docs.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/health` | Health check |
| GET    | `/api/models` | Platform → ICA model id |
| POST   | `/api/generate` | `{thought, platform, options:{invocation, scripts, script_language}}` → **SSE** stage events, then `done` with the skill |
| GET    | `/api/skills` | List active skills |
| GET / DELETE | `/api/skills/{id}` | Read (includes `files[]`, `validation`) / delete |
| PUT / DELETE | `/api/skills/{id}/files/{path}` | Edit `{content}` / delete one file (not `SKILL.md`) |
| POST   | `/api/skills/{id}/validate` | Re-run static checks |
| POST / DELETE | `/api/skills/{id}/install` | Install to `~/.claude/skills` (`{overwrite}`; 409 on conflict) / uninstall |
| POST   | `/api/skills/{id}/archive` | Archive to `skills/.archive/` |
| POST   | `/api/skills/{id}/regenerate` | **SSE**. Regenerate from the original idea (same id). This is also the upgrade path for v1 skills |
| GET    | `/api/skills/{id}/download` | `.zip` of the bundle folder |
| POST   | `/api/skills/{id}/test` | **SSE**. Static checks, then each eval is run and graded |

## Using the skills

| Platform | How to use generated skills |
|----------|------------------------------|
| **Claude Code (personal)** | Click **Install to ~/.claude/skills**. Restart Claude Code if it's already open. Then run `/<skill-name> <args>`, or just describe the task and Claude loads the skill from its description |
| **Claude Code (this project)** | Anthropic bundles are also mirrored to `.claude/skills/` in this repo |
| **Claude.ai** | Download the `.zip`, then go to Settings > Capabilities > Skills > Upload |
| **Gemini** | Mirrored to `.gemini/skills/`, or download the zip. Only spec frontmatter fields are used |
| **ChatGPT** | A single instructions file. Copy it into Custom Instructions or a GPT system prompt |

If a skill includes scripts, check its usage guide for the prerequisites (pip or npm packages) before you use it.

## Generated bundle format

```
<skill-name>/
├── SKILL.md              # frontmatter + concise workflow; links to the files below
├── reference/*.md        # detailed docs, loaded only when needed (one level deep)
├── examples.md           # input/output examples (optional)
├── templates/*           # output templates (optional)
├── scripts/*.py|sh|js    # deterministic helpers: ${CLAUDE_SKILL_DIR}/scripts/...
└── evals/evals.json      # >= 3 scenarios: {query, files, expected_behavior[]}
```

`SKILL.md` frontmatter for Claude Code can use `name`, `description`, `when_to_use`, `argument-hint`, `allowed-tools`, `disable-model-invocation`, `user-invocable`, and related fields. Gemini bundles are limited to the portable spec fields (`name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`).

Names are lowercase kebab-case (at most 64 characters, and must not contain `claude` or `anthropic`). If two skills would share a name, the second one gets a suffix (`-2`, `-3`, ...).

**Safety:** generated scripts are syntax-checked only. The app never executes them, not even during evals. Review each script before you let Claude Code run it.

## License

MIT
