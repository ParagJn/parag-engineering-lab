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
3. Start it with the included `start.sh` (where available), or follow the setup steps in the project README.

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
| [File Compare](File-Compare) | Document Tools | Section-by-section AI comparison of PDF, DOCX, or image files | Azure OpenAI, Streamlit |
| [Document Processor](document_processor) | RAG / Document Tools | Turns DOCX files into chunks ready for a vector database, with image enrichment | Azure OpenAI Vision, Milvus |
| [MD to DOCX](md-to-docx) | Document Tools | Converts Markdown to formatted Word files, including Mermaid diagrams | Streamlit, Python |
| [Interview Coach](Interview-Coach) | Career Tools | Interview practice with three AI agents asking questions and scoring answers | GPT-4, Gemini, Claude, React, FastAPI |
| [Profile Generator](Profile-Generator) | Career Tools | Resume to animated HTML CV, PDF, and LinkedIn helper | Gemini 2.5 Pro, Claude Opus, Playwright |
| [Profile Generator V2](Profile-Generator-V2) | Career Tools | Two-stage LLM CV rebuild with ATS optimization report | Gemini, Claude, React, FastAPI |
| [Skills Generator](Skills-Generator) | Developer Tools | Turns ideas into structured `SKILL.md` files for Claude, Gemini, and Azure OpenAI | Claude, Gemini, Azure OpenAI, React |
| [Strategy Analyzer](Strategy-Analyzer) | Enterprise Strategy | Four-agent review of strategy documents with follow-up chat and an action map | Multi-provider LLMs, React, FastAPI |
| [Project Schedule Tool](Project-Schedule-Tool) | Productivity | Gantt scheduling, critical-path engine, and AI-generated Statements of Work | React, TypeScript, AG Grid, SAP AI Core / IBM ICA |
| [My Own AI Assistant](My-Own-AI-Assistant) | Productivity | Personal chat assistant with document upload and session management | IBM ICA, React, FastAPI |
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
A Streamlit document comparison tool powered by Azure OpenAI. Upload any two files (PDF, DOCX, or image) and get a detailed AI report of the differences, section by section. PDFs are split by page and DOCX files by heading, and images are converted to Markdown first. The report can be downloaded as Markdown.

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
