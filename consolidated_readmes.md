# Consolidated Project Documentation — Parag Engineering Lab

This document aggregates the specifications, features, technology stacks, and orchestration frameworks for all 15 AI-powered applications and utility tools in this repository.

---

## Table of Contents
1. [Agentic Procurement Simulator](#1-agentic-procurement-simulator)
2. [Agentic Post Strategist](#2-agentic-post-strategist)
3. [Article Generator](#3-article-generator)
4. [Interview Coach](#4-interview-coach)
5. [Profile Generator V2](#5-profile-generator-v2)
6. [Profile Generator (V1)](#6-profile-generator-v1)
7. [Project Schedule Tool](#7-project-schedule-tool)
8. [Chat With Database](#8-chat-with-database)
9. [Daily Articles Pages (Morning Edition)](#9-daily-articles-pages-morning-edition)
10. [VoltStream Energy Dashboard](#10-voltstream-energy-dashboard)
11. [Strategy Analyzer](#11-strategy-analyzer)
12. [File Compare](#12-file-compare)
13. [md-to-docx Converter](#13-md-to-docx-converter)
14. [Skills Generator](#14-skills-generator)
15. [Document Processor for Vector Databases](#15-document-processor-for-vector-databases)

---

## 1. Agentic Procurement Simulator
* **Directory**: [Agentic-Procurement](file:///Users/paragjain/dev-works/parag-engineering-lab/Agentic-Procurement)
* **Overview & Value**: Simulates automated B2B contract negotiations between a Buyer (MegaMart Online, powered by Google Gemini) and a Supplier (FreshFizz Consumer Products, powered by Anthropic Claude) with Human-in-the-Loop governance, inventory sync, and a conversational auditor.
* **Tech Stack**:
  - **Frontend**: Vite, React 19, TypeScript, Tailwind CSS v4, Lucide Icons.
  - **Backend**: Python 3.12, FastAPI, Pydantic v2.
  - **Database**: Local flat JSON repositories with global concurrency locks.
* **Orchestration Pattern**: **Bi-directional Conversational Loop**. Gemini (Buyer) and Claude (Supplier) negotiate SKU prices/discounts iteratively.
* **Business Benefit**: Eliminates spreadsheet discrepancies, reduces contract cycle times, binds Stock-Keeping Units (SKUs) directly to negotiation bounds, and ensures transaction visibility via an auditor chatbot.

---

## 2. Agentic Post Strategist
* **Directory**: [Agentic-Post-Strategist](file:///Users/paragjain/dev-works/parag-engineering-lab/Agentic-Post-Strategist)
* **Overview & Value**: Social media strategy scheduler running Google Gemini and Anthropic Claude in parallel to generate comprehensive content calendars, engagement rules, and copywriting structures.
* **Tech Stack**:
  - **Frontend**: React 18, Tailwind CSS, Vite.
  - **Backend**: FastAPI, asyncio, Python 3.11.
* **Orchestration Pattern**: **Parallel Execution with Synthesis**. Splits operational strategy tasks between Gemini and Claude, merging their outputs into a combined 30-day strategy content draft.
* **Business Benefit**: Rapid creation of multi-platform marketing copy, cohesive campaign planning, and automated analytics tags.

---

## 3. Article Generator
* **Directory**: [Article-Generator](file:///Users/paragjain/dev-works/parag-engineering-lab/Article-Generator)
* **Overview & Value**: Full-stack content creation pipeline drafting search-engine-optimized articles from target links.
* **Tech Stack**:
  - **Frontend**: React 18, Axios, Server-Sent Events (SSE) stream listener.
  - **Backend**: FastAPI, Uvicorn, asyncio.
* **Orchestration Pattern**: **Critic-Generator Loop**. Gemini researches and drafts the article. Claude evaluates the quality (1-10) and feeds suggestions back. Rewrites trigger automatically if the score falls below 7.
* **Business Benefit**: Guarantees content standards and tone validation, reduces editorial review overhead, and streams progress in real time.

---

## 4. Interview Coach
* **Directory**: [Interview-Coach](file:///Users/paragjain/dev-works/parag-engineering-lab/Interview-Coach)
* **Overview & Value**: Interactive interview coaching panel providing candidate assessments across behavioral and technical metrics.
* **Tech Stack**:
  - **Frontend**: React 18, Vite, Recharts, Tailwind CSS.
  - **Backend**: FastAPI, Python, HTTPX client.
  - **AI Gateway**: SAP AI Core OAuth routing.
* **Orchestration Pattern**: **Consensus Panel**. GPT-4 outlines base questions. Claude and Gemini refine different question blocks. All three score answers concurrently via `asyncio.gather` for panel feedback.
* **Business Benefit**: Multi-perspective, objective candidate assessments with interactive scoring trend dashboards.

---

## 5. Profile Generator V2
* **Directory**: [Profile-Generator-V2](file:///Users/paragjain/dev-works/parag-engineering-lab/Profile-Generator-V2)
* **Overview & Value**: ATS (Applicant Tracking System) CV optimizer evaluating resume documentation against job specifications.
* **Tech Stack**:
  - **Frontend**: React 18, Tailwind CSS.
  - **Backend**: FastAPI, google-genai, Anthropic SDK.
* **Orchestration Pattern**: **Two-Stage Pipeline**. Gemini extracts structured credential JSON models from CV files. Claude parses the JSON to compile target markdown and responsive HTML CV grids.
* **Business Benefit**: Increases applicant hiring metrics, identifies target vocabulary gaps, and renders printable PDFs.

---

## 6. Profile Generator (V1)
* **Directory**: [Profile-Generator](file:///Users/paragjain/dev-works/parag-engineering-lab/Profile-Generator)
* **Overview & Value**: Single-click resume compilation converting raw candidate descriptions into responsive animated resumes, PDFs, and LinkedIn postings.
* **Tech Stack**:
  - **Frontend**: React 18, Tailwind CSS.
  - **Backend**: FastAPI, pdfplumber, Playwright PDF render engine.
  - **AI Gateway**: SAP AI Core (routing to Claude Opus and Gemini 2.5 Pro).
* **Orchestration Pattern**: **Cascading Extraction**. Gemini parses raw uploads into structured formats, while Claude structures the interactive visual CSS layouts.
* **Business Benefit**: Streamlines personal branding packaging with high-fidelity, context-aware interactive exports.

---

## 7. Project Schedule Tool
* **Directory**: [Project-Schedule-Tool](file:///Users/paragjain/dev-works/parag-engineering-lab/Project-Schedule-Tool)
* **Overview & Value**: Scheduling workbook tracking task dependencies and generating Statements of Work.
* **Tech Stack**:
  - **Frontend**: React 19, Material-UI (MUI) v9, AG Grid, ExcelJS.
  - **Backend**: FastAPI, Topological scheduler, python-docx.
  - **AI Gateway**: SAP AI Core.
* **Orchestration Pattern**: **Hybrid Mathematical/AI scheduler**. Deterministic critical paths are calculated mathematically; variables are then fed to Claude to compile Statement of Work (SoW) contracts.
* **Business Benefit**: Prevents project delays, calculates critical paths automatically, and auto-generates legal drafts.

---

## 8. Chat With Database
* **Directory**: [Chat-With-Database](file:///Users/paragjain/dev-works/parag-engineering-lab/Chat-With-Database)
* **Overview & Value**: Conversational data analytics interface permitting natural language queries against SQL databases.
* **Tech Stack**:
  - **Frontend**: React 19, Tailwind CSS.
  - **Backend**: FastAPI, LangGraph ReAct agent framework, SQLAlchemy.
  - **Database**: PostgreSQL / MySQL.
* **Orchestration Pattern**: **ReAct Agent Loop**. LangGraph agent runs iterative reasoning loops (Introspect Schema -> Draft SQL -> Run Query -> Format Results).
* **Business Benefit**: Democratizes database access for non-technical users, reduces ad-hoc SQL developer requests, and formats output tables.

---

## 9. Daily Articles Pages (Morning Edition)
* **Directory**: [Daily-Articles-Pages](file:///Users/paragjain/dev-works/parag-engineering-lab/Daily-Articles-Pages)
* **Overview & Value**: Curates technical RSS news channels into a formatted typography newspaper.
* **Tech Stack**:
  - **Frontend**: React 19, Tailwind CSS v4, custom magazine layout grids.
  - **Backend**: FastAPI, feedparser, Playwright, SMTP client.
* **Orchestration Pattern**: **Map-Reduce Curation**. Gemini summarizes and tags feeds in parallel (Map). Claude curates the top 10 articles and structures visual spread styles (Reduce).
* **Business Benefit**: Automated, high-quality newsletter curation and publishing, complete with PDF prints and automated email distribution.

---

## 10. VoltStream Energy Dashboard
* **Directory**: [Energy-Dashboard-Monitor](file:///Users/paragjain/dev-works/parag-engineering-lab/Energy-Dashboard-Monitor)
* **Overview & Value**: Utility monitor auditing energy consumption logs and tracing dataset anomalies.
* **Tech Stack**:
  - **Frontend**: React 19, SVG lineage visualization.
  - **Backend**: FastAPI, Pandas, SAP AI Core.
* **Orchestration Pattern**: **Anomaly Diagnostics**. Pandas identifies outlier records; Gemini traces the quarantine root causes and outputs remediation logic.
* **Business Benefit**: High-fidelity utility audit trails, automated pipeline anomaly fixes, and interactive visual data lineage charts.

---

## 11. Strategy Analyzer
* **Directory**: [Strategy-Analyzer](file:///Users/paragjain/dev-works/parag-engineering-lab/Strategy-Analyzer)
* **Overview & Value**: Enterprise consulting analyzer reviewing corporate strategy slide decks and documents.
* **Tech Stack**:
  - **Frontend**: React 18, HTML5 Canvas.
  - **Backend**: FastAPI, python-docx, python-pptx, pypdf, Pillow.
  - **AI Gateways**: SAP AI Core (Claude Opus, Gemini Pro) and Azure OpenAI (GPT-5.4).
* **Orchestration Pattern**: **Specialized Multi-Agent Consensus**. 3 parallel expert agents (Architecture, Cost, Validation) review files; a 4th agent (Synthesizer) merges details into a final report.
* **Business Benefit**: Speeds up corporate due diligence, evaluates cost constraints, and exports visual strategy action maps.

---

## 12. File Compare
* **Directory**: [File-Compare](file:///Users/paragjain/dev-works/parag-engineering-lab/File-Compare)
* **Overview & Value**: Multi-format document diff comparison tool highlighting changes in text, layout, or diagrams.
* **Tech Stack**: Streamlit, Azure OpenAI Vision (GPT-4o), pypdf, python-docx.
* **Orchestration Pattern**: **Comparative Vision Analysis**. Converts uploads to structured Markdown (running OCR on images via GPT-4o Vision) and runs semantic version comparison reviews.
* **Business Benefit**: Simplifies version control reviews for PDF/DOCX agreements and detects differences in visual diagrams.

---

## 13. md-to-docx Converter
* **Directory**: [md-to-docx](file:///Users/paragjain/dev-works/parag-engineering-lab/md-to-docx)
* **Overview & Value**: Document conversion utility converting Markdown files to Microsoft Word (.docx) files.
* **Tech Stack**: Streamlit, python-docx, markdown-it-py, Pillow.
* **Orchestration Pattern**: **Token Tree Rendering Wrapper**. Compiles markdown token syntax directly to MS Word structures; fetches and renders Mermaid diagrams to embedded PNG images.
* **Business Benefit**: Allows developers to compose documentation in Markdown and export formatted documents to non-technical business partners.

---

## 14. Skills Generator
* **Directory**: [Skills-Generator](file:///Users/paragjain/dev-works/parag-engineering-lab/Skills-Generator)
* **Overview & Value**: Code skill builder creating `SKILL.md` configurations for developer tools (like Claude Code CLI, Gemini Gems, or ChatGPT).
* **Tech Stack**:
  - **Frontend**: Vanilla JS, Tailwind CSS, http-server.
  - **Backend**: FastAPI, Anthropic SDK, google-genai.
* **Orchestration Pattern**: **Template-Driven Refinement**. Prompt templates guide the model in structuring the skill schema, generating usage guides, and setting up validation test cases.
* **Business Benefit**: Automates agent configuration, compiles testing suites for custom instructions, and syncs directly to CLI paths.

---

## 15. Document Processor for Vector Databases
* **Directory**: [document_processor](file:///Users/paragjain/dev-works/parag-engineering-lab/document_processor)
* **Overview & Value**: Processing pipeline chunking Word documentation into semantic units for RAG databases (Milvus).
* **Tech Stack**:
  - **Frontend**: React 18, Vite, Tailwind CSS.
  - **Backend**: FastAPI, python-docx, Pillow, Azure OpenAI (Embeddings + Vision).
* **Orchestration Pattern**: **Hierarchical Chunking Pipeline**. Preserves document heading hierarchy as prefix contexts for nested text paragraphs. Vision models caption embedded diagrams.
* **Business Benefit**: High-quality vector store inputs, contextual chunks for RAG searches, and image OCR inclusion.
