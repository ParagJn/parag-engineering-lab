# Document File Comparison Tool (Streamlit + Azure OpenAI)

A simple but powerful 2-file comparison tool for PDF and DOCX.

## Features
- Upload **2 files** (`.pdf` or `.docx`)
- Extract text and split content into sections
  - PDF: sectioned by page
  - DOCX: sectioned by heading style (fallback to paragraph blocks)
- Quick heuristic diff (line-level + section-level)
- Generate a **detailed section-by-section AI report** using Azure OpenAI
- Download report as Markdown
- Runtime behavior configured via `config.json`
- Secrets and endpoints loaded from `.env`

## Project Files
- `app.py` - Streamlit application
- `config.json` - App/document/LLM/report configuration
- `.env.example` - Required environment variables template
- `requirements.txt` - Python dependencies

## Setup
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create `.env` from template:
   ```bash
   cp .env.example .env
   ```
4. Fill `.env` values:
   - `AZURE_OPENAI_API_KEY`
   - `AZURE_OPENAI_ENDPOINT`
   - `AZURE_OPENAI_API_VERSION`
   - `AZURE_OPENAI_DEPLOYMENT`

## Run
```bash
streamlit run app.py
```

## Notes
- If a PDF is image-only/scanned, text extraction may fail without OCR.
- For large documents, content is truncated based on `pdf.max_characters_for_llm` in `config.json`.
