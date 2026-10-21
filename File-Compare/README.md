# File Compare

Compare two files (PDF, Word or image) and get a section-by-section AI report. FastAPI backend, Vite + React + Tailwind frontend, LLM calls through IBM ICA. It replaces the earlier Streamlit + Azure OpenAI version.

## What it does
- Drop in **two files**: `.pdf`, `.docx`, `.png`, `.jpg`, `.jpeg`, `.webp` (any mix of the three kinds)
- Extracts text and splits it into sections
  - PDF: one section per page
  - DOCX: split on heading styles, falling back to blocks of paragraphs
  - Image: converted to markdown by the vision model, then split on markdown headings
- Quick heuristic diff (line level and section level) with similarity scores
- A detailed AI comparison report (executive summary, section-by-section, similarities, differences, missing content, verdict with confidence)
- Collapsible views of the top section differences, raw line changes and the extracted text
- **Side-by-side view**: aligned two-column diff of the extracted text with word-level highlights inside changed lines, a "changes only" mode and previous/next change buttons
- **Saved comparisons**: every finished comparison is saved automatically. The sidebar lets you search, reopen, rename and delete them. The report, stats and extracted text are kept; the original files are not
- Download the report as Markdown

## Run
```bash
./start.sh
```
Opens http://localhost:5240 (frontend) with the API on http://localhost:8060. It also runs from the Lab Launcher (root `./start.sh`), where it appears under **Document Tools**.

## Setup
1. `cp backend/.env.example backend/.env`
2. Fill in `IBM_ICA_ENDPOINT` and `IBM_ICA_API_KEY` (`IBM_ICA_MODEL_ID` defaults to `claude-opus-5-5`)

`start.sh` installs missing Python packages into the shared venv (`/Users/paragjain/dev-works/myenv`) and runs `npm install` on first start.

## Layout
```
backend/app/
  main.py             API: /api/status, /api/compare, /api/comparisons (list, get, rename, delete, diff)
  store.py            SQLite storage for saved comparisons (backend/data/file_compare.db, gitignored)
  diffview.py         aligned side-by-side diff with word-level segments
  documents.py        PDF / DOCX / image-markdown extraction and sectioning
  compare.py          line + section diffs and the report prompt
  llm.py              IBM ICA calls (report + image-to-markdown), content-filter fallback
  ibm_ica_client.py   stdlib IBM ICA client shared with the sibling projects
  config.py           settings read from backend/.env
frontend/src/         React UI (App.jsx, api.js, components/DiffView, components/HistorySidebar)
```

## Settings (backend/.env, all optional except the ICA credentials)
| Variable | Default | Meaning |
|---|---|---|
| `IBM_ICA_FALLBACK_MODEL_ID` | `claude-sonnet-5` | Retried once if a reply is blocked by the content filter |
| `DATA_DIR` | `backend/data` | Where the saved-comparisons database lives |
| `MAX_UPLOAD_MB` | 50 | Per-file upload limit |
| `MAX_PDF_PAGES` | 300 | Pages read per PDF |
| `MAX_CHARS_FOR_LLM` | 180000 | Text sent to the model per file; longer files are cut and the UI says so |
| `REPORT_MAX_OUTPUT_TOKENS` | 7000 | Report length cap |
| `IMAGE_MAX_OUTPUT_TOKENS` | 3000 | Image-to-markdown length cap |

## Notes
- Scanned (image-only) PDFs have no extractable text. Upload the pages as images instead.
- Images over about 3.5 MB are downscaled before being sent to the vision model.
- Uploaded files are processed in memory and never written to disk. Only the extracted text and the report are saved.
- Deleting a comparison from the sidebar removes it from the database for good.
