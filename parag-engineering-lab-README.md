# Parag Engineering Lab

A collection of AI-powered tools and utilities built for real-world engineering and productivity workflows.

---

## Agentic Post Strategist

An agentic social media strategy tool powered by both Google Gemini and Anthropic Claude running in parallel. It generates comprehensive social media strategies, 30-day content calendars, viral hook formulas, engagement plans, and analytics insights — all synthesized into a single execution-ready output tailored to your niche and audience.

---

## Article Generator

A full-stack app that generates high-quality articles from user-provided source URLs. Google Gemini researches and drafts the article while Anthropic Claude reviews and scores it. If the score falls below a threshold, the pipeline auto-retries with Claude's feedback applied. A manual "Apply Claude Suggestions" refinement option is also available, with real-time progress streamed to the UI.

---

## File Compare

A Streamlit-based document comparison tool powered by Azure OpenAI. Upload any two files (PDF, DOCX, or image) and get a detailed section-by-section AI-generated diff report. Content is extracted and segmented intelligently — PDFs by page, DOCX by heading, images by converting to markdown first — and the report can be downloaded as Markdown.

---

## Document Processor

A document processing pipeline that converts `.docx` files into vector-ready chunks for RAG (Retrieval Augmented Generation) applications and vector databases. It preserves document hierarchy (headings, sections, paragraphs, tables, images) and optionally uses Azure OpenAI Vision to enrich image content with OCR, captions, and markdown conversion. Output is formatted for direct ingestion into Milvus or similar vector databases.

---

## MD to DOCX Converter

A Streamlit utility that converts Markdown (`.md`) files to professionally formatted Word (`.docx`) documents. It supports tables, code blocks, lists, blockquotes, embedded images, and renders Mermaid diagrams as PNG images. Multiple files can be uploaded at once, and all converted documents can be bulk-downloaded as a ZIP.

---

## Chat With Database

A full-stack AI-powered application that lets you converse with your relational database in plain English. Ask questions, explore schemas, run analytics, and get structured results — all without writing a single line of SQL. It uses a LangGraph ReAct agent backed by Anthropic Claude, equipped with tools to introspect the schema, construct queries, and return human-readable answers. Supports PostgreSQL and MySQL.

---

## Daily Articles Pages

An AI-curated daily tech magazine generator. Select from 10 top tech news sources (or blend up to 5), and get a beautifully rendered, self-contained HTML magazine with editorial-grade content, 10 distinct visual spread styles, and full SEO markup. Gemini 2.0 Flash enriches and ranks stories from RSS feeds, while Claude Sonnet writes the editorial copy. Includes PDF export via Playwright, an email newsletter with the PDF attached, and a built-in archive system to browse, reload, and regenerate past editions.

---

## Profile Generator

An AI-powered tool that turns your resume documents and public profile links into a polished HTML CV, a print-ready PDF, and a LinkedIn copy-paste helper — all in one click. Gemini 2.5 Pro extracts a structured JSON profile from your uploads, Claude Opus generates the animated HTML resume and LinkedIn helper, and Playwright renders a pixel-perfect PDF. An iterative "Request Changes" prompt lets you refine all three outputs with context preserved.

---

## Skills Generator

An AI-powered skill definition generator that converts your ideas into fully structured, production-ready skill files for Anthropic (Claude), Google Gemini, and Azure OpenAI. Skills are saved as versioned `SKILL.md` files, auto-synced to `.claude/skills/` for immediate use in the Claude Code CLI, and downloadable as a ZIP for upload to Claude.ai. Includes one-click test case generation, full lifecycle management (regenerate, archive, delete), and a persistent skill library sidebar.

---

## Architect Solutions Demo

This repository will contain short product videos of some of the professional tools that I have built leading the asset engineering services at IBM. These videos will showcase the capabilities of the tool/asset and how it can be used in real-world scenarios.
