# Skills Generator — Project Context

## Summary

A full-stack AI skill generator. It turns a user's idea into a full skill bundle (SKILL.md, reference docs, scripts, templates, and evals). Claude Code is the primary target, Gemini gets spec-only bundles, and ChatGPT gets a single instructions file. **IBM ICA is the only model provider**; no OpenAI, Anthropic, or Google SDKs are used.

## Tech Stack

- **Backend**: Python + FastAPI, API only, run with Uvicorn on `127.0.0.1:8000`
- **Frontend**: Vite + Tailwind CSS v3 + vanilla JS on `localhost:5173`. `/api` is proxied to the backend.
- **LLM**: IBM ICA chat completions via `backend/ibm_ica_client.py` (urllib, no SDK)
- **Python venv**: `/Users/paragjain/dev-works/myenv` (shared, not project-local)

## How to Run

```bash
./start.sh     # backend :8000 + frontend :5173 (opens browser); Ctrl+C stops both
```

## Configuration

- The single config file is the project-root `.env`, loaded by `backend/config.py`. There is no `backend/.env`.
  - Required: `IBM_ICA_API_KEY`, `IBM_ICA_ENDPOINT`.
  - Models: `IBM_ICA_MODEL_ID` (default `claude-opus-5-5`, used for Anthropic and ChatGPT skills) and `IBM_ICA_GEMINI_MODEL_ID` (default `gemini-3.7-flash`, used for Gemini skills).
  - Optional: `IBM_ICA_INSECURE_TLS`, `MODEL_TIMEOUT` (300), `MAX_TOKENS` (8000), `GENERATION_MAX_TOKENS` (16000), `MAX_REPAIR_ROUNDS` (2), `CLAUDE_PERSONAL_SKILLS_DIR` (`~/.claude/skills`).
- `config.MODEL_CHOICES` maps each platform to its ICA model id.

## Backend modules

| File | Role |
|------|------|
| `main.py` | FastAPI routes under `/api`. `/generate`, `/regenerate`, and `/test` stream SSE. Store errors map NotFound → 404, InstallConflict → 409, ValueError → 400 |
| `config.py` | Settings + `validate()` + directory setup |
| `model_service.py` | Singleton wrapping `IBMICAClient`; `generate(prompt, platform, *, system, max_tokens)` runs the sync client in a thread |
| `ibm_ica_client.py` | Copied from My-Own-AI-Assistant; keep it identical |
| `generator.py` | Pipeline events: blueprint JSON → bundle (`<<<FILE: path>>>` blocks) → validate → repair (≤ MAX_REPAIR_ROUNDS) → usage notes → save. It also has the eval pipeline (run and grade each scenario, concurrency 2) |
| `prompts.py` | Authoring guide plus the blueprint / bundle / single-file / repair / usage-notes / eval prompts (`{{key}}` templating) |
| `skill_spec.py` | Spec constants: name regex and reserved words, the description limit, spec vs Claude Code fields, allowed dirs and extensions, file limits, `FORMAT_VERSION=2` |
| `bundle.py` | `parse_bundle` (rejects unsafe paths), `serialize_bundle`, frontmatter split, and the name and field helpers |
| `validator.py` | `validate_bundle(files, platform)` → `{errors, warnings, passed, ok}`. Scripts are syntax-checked only (`ast`, `bash -n`, `node --check`) and **never executed** |
| `skill_store.py` | Multi-file storage, `.metadata.json` (atomic writes, lock), sync to `.claude/skills` / `.gemini/skills` / the personal install, zip, and install/uninstall |

## Storage rules

- Each skill is the folder `skills/<skill_dir>/`. Metadata lives in `skills/.metadata.json`, keyed by an 8-character id.
- Bundles have `format_version: 2`. Legacy entries without that field are treated as v1 (single file) and get an Upgrade button, which runs regenerate with the same id.
- `skill_dir` is the sanitized kebab-case `name:`, made unique with `-2`, `-3`, and so on. The frontmatter `name:` is rewritten to match.
- The saved metadata includes `validation`, `options`, `usage_notes`, `installed_path`, and `evals_last_run`. `evals_last_run` is cleared whenever the files change.
- `scripts/*` get chmod +x on disk and the exec bit in the zip.
- **Regenerate** builds the new version first. If that fails, the old version is untouched.
- **Personal install** copies the bundle to `~/.claude/skills/<skill_dir>` along with a `.skills-generator` marker. Any folder without that marker gives a 409 unless `overwrite` is set. Edits, renames, and regenerates re-sync the install. Delete and archive remove it.
- **Delete / archive** never remove a folder that another live skill still references.
- **Archive** moves the folder to `skills/.archive/<skill_dir>-<id>/`.

## Frontend

- `index.html` uses `data-action="..."` attributes. `src/main.js` wires them up through a single delegated click handler.
- `src/api.js`: `api()` and `streamSSE()`, which reads POST SSE through a fetch ReadableStream. `src/bundle-view.js`: file tree, viewer/editor, validation panel. `src/render.js`: marked + highlight.js.
- Markdown is rendered with `marked` and sanitized with DOMPurify. Skill names are HTML-escaped in the sidebar.
- The platform card subtitles show the actual ICA model, fetched from `/api/models`.

## Pending / Future Improvements

- Adding new files to a bundle from the UI
- Sidebar search/filter
- View/restore archived skills
- Favicon
