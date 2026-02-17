# PDF File Comparison Tool (Streamlit + Azure OpenAI)

A simple but powerful 2-file PDF comparison tool.

## Features
- Upload **2 PDF files**
- Extract text from both files
- Compute quick structural diff stats locally
- Generate a **detailed, formatted AI report** using Azure OpenAI
- Download report as Markdown
- Runtime behavior configured via `config.json`
- Secrets and endpoints loaded from `.env`

## Project Files
- `app.py` - Streamlit application
- `config.json` - App/PDF/LLM/report configuration
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
- For large PDFs, content is truncated based on `pdf.max_characters_for_llm` in `config.json`.
