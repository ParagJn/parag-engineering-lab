# Skills Generator

An elegant AI-powered skill definition generator that converts your ideas into fully structured, production-ready skill files for **Anthropic (Claude)**, **Google Gemini**, and **Azure OpenAI (GPT-5.4)**.

![Node.js](https://img.shields.io/badge/Node.js-Frontend-339933?logo=node.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-UI-06B6D4?logo=tailwindcss&logoColor=white)

---

## Features

- **Multi-platform support** — Generate skills for Anthropic, Gemini, or Azure OpenAI GPT-5.4
- **Anthropic-ready output** — Skills saved as `skill-name/SKILL.md` directories, downloadable as `.zip` for direct upload to Claude.ai
- **Claude Code integration** — Anthropic skills are automatically copied to `.claude/skills/` for immediate use in the Claude Code CLI
- **Copy to Clipboard** — One-click copy of skill content for pasting into Gemini Gems or ChatGPT Custom Instructions
- **Usage guide** — Auto-generated beginner-friendly instructions for every skill
- **Test skills** — One-click test case generation and execution against the target LLM
- **Sidebar** — Persistent skill library for quick access and reuse
- **Regenerate / Archive / Delete** — Full lifecycle management
- **Responsive UI** — Optimized for desktop, tablet, and mobile screens
- **Google-themed design** — Clean interface with Material Symbols and Google color palette

## Tech Stack

| Layer    | Technology                                          |
|----------|-----------------------------------------------------|
| Backend  | Python, FastAPI, Uvicorn                            |
| Frontend | HTML, Tailwind CSS, Vanilla JS, http-server         |
| LLMs     | Azure OpenAI (GPT-5.4), Anthropic (Claude Sonnet), Google Gemini 2.0 Flash |

## Project Structure

```
Skills-Generator/
├── backend/
│   ├── main.py              # FastAPI app — API routes, LLM integration
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── package.json          # Node/Tailwind config + http-server dev scripts
│   ├── tailwind.config.js    # Google-themed color palette
│   ├── postcss.config.js
│   ├── src/
│   │   └── input.css         # Tailwind directives
│   └── public/
│       ├── index.html        # Responsive single-page UI
│       └── app.js            # Client-side application logic
├── skills/                   # Generated skills (each as <name>/SKILL.md)
├── .claude/
│   └── skills/               # Auto-synced Anthropic skills for Claude Code CLI
├── .env                      # API keys (not committed)
├── .gitignore
└── README.md
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- API keys: Anthropic, Google Gemini, and Azure OpenAI (GPT-5.4 deployment)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/ParagJn/parag-engineering-lab.git
cd parag-engineering-lab/Skills-Generator
```

### 2. Configure environment variables

Create a `.env` file in the project root with your API keys:

```env
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Google Gemini
GEMINI_API_KEY=AIza...

# Azure OpenAI (GPT-5.4)
AZURE_OPENAI_GPT54_BASE=https://<your-resource>.openai.azure.com
AZURE_OPENAI_GPT54_KEY=<your-key>
AZURE_OPENAI_GPT54_VERSION=2025-04-01-preview
AZURE_OPENAI_GPT54_DEPLOYMENT=gpt-5.4-common
```

### 3. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 4. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 5. Run the application

**Backend** (in one terminal):
```bash
source venv/bin/activate
cd backend
uvicorn main:app --reload --port 8000
```

**Frontend dev server** (in another terminal):
```bash
cd frontend
npm run dev
```

Open **http://localhost:3000** in your browser.

> The frontend dev server proxies all `/api` requests to the backend on port 8000.

## Usage

1. Select a target LLM platform (Anthropic, Gemini, or Azure OpenAI)
2. Describe your skill idea in the text area
3. Click **Generate Skill** — the AI creates a structured skill definition
4. Review the skill along with the auto-generated **Usage Guide**
5. Click **Test Skill** to run an automated test against the target LLM
6. Use the action buttons:
   - **Copy** — Copy raw skill content to clipboard (for Gemini Gems / ChatGPT Custom Instructions)
   - **Download** — Export as `.zip` (for drag-and-drop upload to Claude.ai Settings > Features)
   - **Regenerate** — Recreate the skill from the original idea
   - **Archive / Delete** — Manage the skill lifecycle
7. Access previously generated skills from the sidebar

## Platform-Specific Usage

| Platform | How to use generated skills |
|----------|------------------------------|
| **Anthropic (Claude.ai)** | Download `.zip` → Settings > Features > Upload skill |
| **Anthropic (Claude Code)** | Auto-synced to `.claude/skills/` — available immediately in CLI |
| **Gemini** | Copy to clipboard → Create a Gem → Paste into system instructions |
| **Azure OpenAI / ChatGPT** | Copy to clipboard → Custom Instructions or GPT system prompt |

## Generated Skill Format

Each skill is saved as a directory `skills/<name>/SKILL.md` with YAML frontmatter:

```markdown
---
name: skill-name-in-kebab-case
description: One-line description of what this skill does and when to use it
license: Complete terms in LICENSE.txt
---

# Skill Title

## Overview
## Core Framework
## Features
## Output Format
## Instructions
## Constraints
```

## License

MIT
