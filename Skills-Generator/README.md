# Skills Generator

An elegant AI-powered skill definition generator that converts your ideas into fully structured, production-ready skill files for **Anthropic (Claude)**, **Google Gemini**, and **ChatGPT (GPT-4o)**.

![Node.js](https://img.shields.io/badge/Node.js-Frontend-339933?logo=node.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-UI-06B6D4?logo=tailwindcss&logoColor=white)

---

## Features

- **Multi-platform support** — Generate skills for Anthropic, Gemini, or ChatGPT with a single click
- **Usage guide** — Auto-generated beginner-friendly instructions for every skill
- **Test skills** — One-click test case generation and execution against the target LLM
- **Sidebar** — Persistent skill library for quick access and reuse
- **Download** — Export any skill as a `.md` file
- **Regenerate / Archive / Delete** — Full lifecycle management
- **Responsive UI** — Optimized for desktop, tablet, and mobile screens
- **Google-themed design** — Clean interface with Material Symbols and Google color palette

## Tech Stack

| Layer    | Technology                  |
|----------|-----------------------------|
| Backend  | Python, FastAPI, Uvicorn    |
| Frontend | HTML, Tailwind CSS, Vanilla JS |
| LLMs     | OpenAI, Anthropic, Google Generative AI |

## Project Structure

```
Skills-Generator/
├── backend/
│   ├── main.py              # FastAPI app — API routes, LLM integration
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── package.json          # Node/Tailwind config
│   ├── tailwind.config.js    # Google-themed color palette
│   ├── postcss.config.js
│   ├── src/
│   │   └── input.css         # Tailwind directives
│   └── public/
│       ├── index.html        # Responsive single-page UI
│       └── app.js            # Client-side application logic
├── skills/                   # Generated skill .md files (output)
├── .env                      # API keys (not committed)
├── .gitignore
└── README.md
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- API keys for at least one of: OpenAI, Anthropic, Google Gemini

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd Skills-Generator
```

### 2. Configure environment variables

Create a `.env` file in the project root with your API keys:

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
```

### 3. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 4. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 5. Run the application

```bash
source venv/bin/activate
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000** in your browser.

## Usage

1. Select a target LLM platform (Anthropic, Gemini, or ChatGPT)
2. Describe your skill idea in the text area
3. Click **Generate Skill** — the AI creates a structured skill definition
4. Review the skill along with the auto-generated **Usage Guide**
5. Click **Test Skill** to run an automated test against the target LLM
6. Use the action buttons to **Download**, **Regenerate**, **Archive**, or **Delete**
7. Access previously generated skills from the sidebar

## Generated Skill Format

Each skill is saved as a `.md` file in the `skills/` folder with this structure:

```markdown
---
name: skill-name-in-kebab-case
description: One-line description
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
