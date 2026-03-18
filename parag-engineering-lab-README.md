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

## Architect Solutions Demo

This repository will contain short product videos of some of the professional tools that I have built leading the asset engineering services at IBM. These videos will showcase the capabilities of the tool/asset and how it can be used in real-world scenarios.
