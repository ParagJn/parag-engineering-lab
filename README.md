# Parag Engineering Lab

A collection of AI-powered tools and utilities built for real-world engineering and productivity workflows, covering multi-agent pipelines, LLM orchestration, and full-stack products.

🌐 **Project showcase:** [paragjn.github.io/parag-engineering-lab](https://paragjn.github.io/parag-engineering-lab/) · 🏗️ [Architecture overview](architecture.html) · 💼 [LinkedIn](https://www.linkedin.com/in/paragjn)

---

> [!IMPORTANT]
> **Prototypes only, not production-ready.**
> Every project in this repository is a **prototype**. Each one is a smaller-scale version of the larger projects, and the kinds of projects, that I have led for my clients. They show architecture patterns, agent designs, and user experience ideas. They have **not** been hardened for production: security reviews, scalability testing, and full error handling are not done.

## About this repository

These prototypes are **ready to try**. Most of them can be run locally once you set up the **LLM model configuration**: provider, API keys or endpoints, and model names. This is usually done in each project's `.env` / config file. Depending on the project, supported providers include Anthropic Claude, Google Gemini, Azure OpenAI, SAP AI Core, and IBM ICA.

To use a project:

1. Open the project folder and read its own `README.md`.
2. Update the LLM model config (`.env`, `config.py`, or similar) with your provider credentials and model IDs.
3. Start it with the included `start.sh` (where available), or follow the setup steps in the project README. Or skip all of that and start everything at once with the [Lab Launcher](#-new-lab-launcher--one-dashboard-for-all-the-apps) below.

---

## 🚀 New: Lab Launcher, one dashboard for all the apps

> [!TIP]
> **New feature alert.** The lab now has a [Homer](https://github.com/bastienwirtz/homer)-style launcher dashboard. Run one command, open one page, and click a card to open any app. No more hunting for each `start.sh`, typing URLs, or remembering which app lives on which port.

```bash
./start.sh            # from the repo root
```

Then open **http://localhost:8999**.

**What you get**

- **One command starts everything.** The launcher serves the dashboard and runs each enabled app's own `start.sh` in the background. Logs go to `launcher/logs/`.
- **Click to open.** Apps show as cards grouped by category, with a search box. Clicking a card opens that app in a new tab.
- **Live status dots.** Green means the app is up, red means it is down. They refresh every few seconds, so you can watch each app come up while its frontend builds.
- **Clean shutdown.** Press `Ctrl+C` and every app is stopped with a short grace period, then force-stopped if it hangs. Every port is released, and the terminal reports what happened. Then it asks whether to stop the dashboard too: `n` leaves the page running, `y` stops it. Press `Ctrl+C` a second time to force an immediate stop.
- **Responsive page.** The banner scales with the window, and on phones it switches to a compact logo header.
- **No new dependencies.** It uses `python3` and plain HTML/JS, with no Docker, no npm install, and no extra services.

**Ports**

Every app has its own backend and frontend ports, so they can all run at the same time.

| App | Backend | Frontend |
|---|---|---|
| My Own AI Assistant | 8000 | 5173 |
| Hero Motion Studio | 8010 | 5180 |
| Data Story Studio | 8020 | 5190 |
| Project Schedule Tool | 8030 | 5200 |
| Daily Articles Pages | 8040 | 5210 |
| Strategy Analyzer | 8050 | 5220 |
| MD to DOCX (frontend only) | n/a | 5230 |
| File Compare | 8060 | 5240 |
| Diagram Studio | 8070 | 5250 |
| Launcher dashboard | | 8999 |

**Adding or renaming an app.** Edit [`launcher/config.json`](launcher/config.json). Each entry is a few lines:

```json
{
  "name": "Data Story Studio",
  "subtitle": "Upload CSV/Excel and get an AI-built, animated dashboard",
  "group": "Analytics",
  "dir": "Data-Story-Studio",
  "start": "./start.sh",
  "url": "http://localhost:5190",
  "ports": [8020, 5190],
  "enabled": true
}
```

Set `"enabled": false` to hide an app from startup. The launcher refuses to start an app whose ports another enabled app already uses, so give each new app its own pair. Each app's own prerequisites (virtual environment, `.env` / LLM configuration) still apply.

---

## Projects at a glance

| Project | Category | What it does | Key tech |
|---|---|---|---|
| [Agentic Procurement](Agentic-Procurement) | Multi-Agent / Supply Chain | Buyer and supplier AI agents negotiate procurement deals, with human-in-the-loop approval | Gemini, Claude, React, FastAPI |
| [Agentic Post Strategist](Agentic-Post-Strategist) | Content & Social | Social media strategy and 30-day content calendar from parallel LLMs | Gemini, Claude, React, FastAPI |
| [Article Generator](Article-Generator) | Content | Writes articles from source URLs, then reviews and scores them with an automatic retry loop | Gemini, Claude, FastAPI |
| [Chat With Database](Chat-With-Database) | Data & Analytics | Ask questions about a relational DB in plain English, no SQL needed | Claude, LangGraph, PostgreSQL/MySQL, React |
| [Daily Articles Pages](Daily-Articles-Pages) | Content | AI-curated daily tech magazine with PDF and email export | Gemini, Claude, Playwright |
| [Energy Dashboard Monitor (VoltStream)](Energy-Dashboard-Monitor) | Data Platform | AI-native data quality, lineage, and anomaly detection for energy and utilities | AI/ML, Python, React |
| [File Compare](File-Compare) | Document Tools | Section-by-section AI comparison of PDF, DOCX, or image files, with a side-by-side view and saved history | IBM ICA, FastAPI, React, Tailwind, SQLite |
| [Diagram Studio](Diagram-Studio) | Document Tools | Turns a Markdown, text or Word document into the diagrams it contains, with zoom, history and animated SVG export | Claude via IBM ICA, FastAPI, React, ELK, SQLite |
| [Document Processor](document_processor) | RAG / Document Tools | Turns DOCX files into chunks ready for a vector database, with image enrichment | Azure OpenAI Vision, Milvus |
| [MD to DOCX](md-to-docx) | Document Tools | Converts Markdown to formatted Word files, including Mermaid diagrams | Streamlit, Python |
| [Interview Coach](Interview-Coach) | Career Tools | Interview practice with three AI agents asking questions and scoring answers | GPT-4, Gemini, Claude, React, FastAPI |
| [Profile Generator](Profile-Generator) | Career Tools | Resume to animated HTML CV, PDF, and LinkedIn helper | Gemini 2.5 Pro, Claude Opus, Playwright |
| [Profile Generator V2](Profile-Generator-V2) | Career Tools | Two-stage LLM CV rebuild with ATS optimization report | Gemini, Claude, React, FastAPI |
| [Skills Generator](Skills-Generator) | Developer Tools | Turns ideas into structured `SKILL.md` files for Claude, Gemini, and Azure OpenAI | Claude, Gemini, Azure OpenAI, React |
| [Strategy Analyzer](Strategy-Analyzer) | Enterprise Strategy | Four-agent review of strategy documents with follow-up chat and an action map | Multi-provider LLMs, React, FastAPI |
| [Project Schedule Tool](Project-Schedule-Tool) | Productivity | Gantt scheduling, critical-path engine, and AI-generated Statements of Work | React, TypeScript, AG Grid, SAP AI Core / IBM ICA |
| [My Own AI Assistant](My-Own-AI-Assistant) | Productivity | Personal chat assistant with document upload and session management | IBM ICA, React, FastAPI |
| [Data Story Studio](Data-Story-Studio) | Data & Analytics | Upload CSV/Excel and get an AI-built, animated dashboard that tells the story in the data, plus an executive summary | Claude via IBM ICA, DuckDB, React, ECharts, FastAPI |
| [Hero Motion Studio](hero-motion-studio) | Presentation Design | Turns a short brief into an animated slide hero, exported as PNG, MP4, GIF or PPTX | Claude via IBM ICA, React, Canvas, FastAPI |
| [TalentFlow](TalentFlow) | HR Intelligence | Recruiting pipeline and hiring-metrics dashboard (front-end prototype) | JavaScript, Chart.js |
| [Architect Solutions Demo](Architect-Solutions-Demo) | Showcase | Short product videos of professional tools built while leading asset engineering services | Video |

---

## Project details

### 🤝 Agentic Procurement
A multi-agent business simulation of automated procurement negotiations. A **Buyer** agent (Gemini) and a **Supplier** agent (Claude) go through a 6-step lifecycle: request for quote, fulfillment proposal, buyer negotiation, supplier counter-proposal, final acceptance, and PO/invoicing. Includes **human-in-the-loop** governance (a person can edit drafts, prices, and quantities), SKU-level counter-offers, a cost-savings scorecard, low-stock auto-replenishment, and an interactive **AI Negotiation Auditor** chat. A mock mode lets the full pipeline run without API keys.

### 📣 Agentic Post Strategist
A social media strategy engine that runs Gemini and Claude in parallel. It generates full strategies, 30-day content calendars, viral hook formulas, engagement plans, and analytics insights. The results are combined into one output tailored to your niche and audience that you can act on directly.

### ✍️ Article Generator
Generates high-quality articles from source URLs. Gemini researches and drafts, and Claude reviews and scores the draft. If the score is below a threshold, the pipeline retries automatically using Claude's feedback. There is also a manual "Apply Claude Suggestions" option for further refinement, and progress streams to the UI in real time.

### 🗄️ Chat With Database
Ask questions about your relational database in plain English. A **LangGraph ReAct agent** backed by Claude reads the schema, builds the queries, and returns answers people can read, with no SQL required. Supports PostgreSQL and MySQL.

### 📰 Daily Articles Pages
An AI-curated daily tech magazine generator. Pick from 10 top tech news sources, or mix up to 5. Gemini enriches and ranks RSS stories, and Claude writes editorial copy for 10 different visual spread styles. Features SEO markup, PDF export via Playwright, an email newsletter, and an archive of past editions.

### ⚡ Energy Dashboard Monitor (VoltStream)
An AI-powered data platform prototype for the energy and utilities sector. It shows how organizations can modernize legacy data infrastructure to support AI at scale. It uses **generative AI to fix data quality issues** with explanations, **AI-generated data lineage** that pinpoints where a pipeline failed, and **ML-based anomaly detection**, plus pipeline run history and an AI explainability log.

### 🔀 File Compare
A document comparison tool (FastAPI + React + Tailwind) powered by IBM ICA. Upload any two files (PDF, DOCX, or image) and get a detailed AI report of the differences, section by section. PDFs are split by page and DOCX files by heading, and images are converted to Markdown first. An aligned side-by-side view highlights changes word by word, finished comparisons are saved to a searchable history, and the report can be downloaded as Markdown.

### 🧩 Diagram Studio
Hand it a Markdown, text or Word document (or paste text) and get back the diagrams it contains. Claude via IBM ICA plans which diagrams the document supports (architecture, flowchart, state, sequence, timeline or quadrant) and returns a small validated spec for each. It never sees coordinates: the browser lays graphs out with ELK and draws editorial-style SVG, inspired by [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design). You can zoom and pan (with a full-window view), reopen past documents from a saved history, redraw a diagram with a plain-language instruction, and export SVG or PNG. An optional animated SVG is built from a fixed set of CSS effects (entrances, flowing dots, pulses, a step-by-step walkthrough), so the file needs no JavaScript.

### 📑 Document Processor
A pipeline that converts `.docx` files into chunks ready for **RAG** and vector databases. It keeps the document structure (headings, sections, tables, images). It can optionally use Azure OpenAI Vision to add OCR text, captions, and Markdown versions of images. Output is formatted for direct loading into Milvus or similar vector databases.

### 📝 MD to DOCX
A Streamlit utility that converts Markdown to well-formatted Word documents. It supports tables, code blocks, lists, blockquotes, embedded images, and **Mermaid diagrams rendered as PNG**. You can upload several files at once and download all results as a ZIP.

### 🎤 Interview Coach
An interview preparation platform with three AI coaches: **GPT-4, Gemini, and Claude**. Together they produce the top interview questions for your role, company, and interview type (Technical, Leadership, Behavioural, Salary Negotiation). Each agent scores every answer independently. At the end you get one combined feedback report, and a progress dashboard tracks your results across sessions.

### 🪪 Profile Generator
Turns resume documents and profile links into a polished **animated HTML CV**, a print-ready **PDF**, and a **LinkedIn copy-paste helper** in one click. Gemini 2.5 Pro extracts a structured profile, Claude Opus writes the outputs, and Playwright renders the PDF. You can keep refining the results with "Request Changes" prompts, and earlier context is kept.

### 🪪 Profile Generator V2
A rebuild with a true two-stage LLM pipeline. Gemini does research and extracts a profile grounded in your source material. Claude then rewrites it as a professional CV. Outputs are an HTML CV, a Markdown CV, a JSON profile, an **ATS optimization report**, and a research summary.

### ⚙️ Skills Generator
Turns ideas into structured `SKILL.md` files ready for **Claude, Gemini, and Azure OpenAI**. Skills are versioned, copied automatically into `.claude/skills/` for Claude Code, and can be downloaded as a ZIP for Claude.ai. Includes one-click test case generation and a skill library you can manage.

### 🧭 Strategy Analyzer
A multi-agent tool for reviewing enterprise strategy documents. Upload a PDF, DOCX, or PPTX. Four agents from two providers review it, each from a different angle: **architecture, cost, validation, and synthesis**. They produce one Markdown report based on evidence from the document, focused on reaching the target state, reducing cost, and shortening turnaround time. You can ask follow-up questions in chat and view a visual strategy action map.

### 📅 Project Schedule Tool
An AI-assisted project scheduling tool. It calculates the critical path, handles weekends in date calculations, and shows a split grid with Gantt timeline in AG Grid. It can also generate **Statements of Work** with a choice of AI provider (SAP AI Core or IBM ICA) and export them to Word. Includes draft management, auto-save, and Excel export.

### 💬 My Own AI Assistant
A clean chat assistant, similar to ChatGPT, built on IBM ICA model infrastructure. Features include managing multiple conversations, uploading documents (TXT, MD, PDF, DOCX), streaming Markdown responses with syntax-highlighted code, web search, and local JSON storage.

### 📊 Data Story Studio
Upload one or more **CSV or Excel files** and get an **animated, explorable dashboard that tells the story in the data**. A readiness gate checks volume, how the files link and data quality before anything is built. A deterministic engine then scores about 25 candidate insights (trends, anomalies, drivers, concentration, correlations), and Claude (via IBM ICA) arranges them into a narrative. A **number guard** drops any sentence citing a figure the data doesn't contain. You can filter by clicking, ask questions in plain English, redraw panels, preview the raw data, and export an interactive HTML or PDF report or a board-ready **Executive Summary** (Markdown or PDF).

### 🟠 Hero Motion Studio
Turns a few lines of text into an **animated hero for a presentation slide**. One accent dot drives a looping motion film: a UI toggle, the hero word, a stat (spring graph, bars, counter or progress ring), a shape morph, kinetic words, a halftone reveal and an end card. Scenes can be switched off and paced, sizes cover full, half, square and banner slides, and exports are rendered frame by frame to **PNG, MP4, GIF or a ready-made PPTX**. Claude (via IBM ICA) can write all the copy from a short brief.

### 👥 TalentFlow
A recruiting dashboard that makes talent acquisition workflows easier. It shows pipeline stages, candidate analytics, and hiring metrics in a clean, interactive UI. Built as a front-end prototype.

### 🎬 Architect Solutions Demo
Short product videos of professional tools and assets built while leading asset engineering services. They show what each tool can do and how it applies in real situations.

---

## Common tech stack

- **LLM providers:** Anthropic Claude, Google Gemini, OpenAI / Azure OpenAI, SAP AI Core, IBM ICA
- **Agent frameworks:** LangGraph, custom multi-agent orchestration
- **Backend:** Python, FastAPI, Streamlit
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, Material-UI, AG Grid
- **Tooling:** Playwright (PDF rendering), python-docx, ExcelJS, Milvus (vector DB)

---

## Disclaimer

All projects here are **prototypes** meant for demonstration, learning, and to speed up client solution design. They are provided as-is, with no warranty. Before using any part of them in production, do a proper security review, handle secrets correctly, add tests, and harden the code for scale.
