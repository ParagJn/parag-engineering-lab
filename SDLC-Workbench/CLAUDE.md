# SDLC Workbench (prototype)

A demoable multi-agent prototype that runs a small software project through the whole lifecycle:
Setup → Requirements → Design → Architecture → Build & Test → Deploy → BAU Handover.
Agents run on Claude Sonnet, Claude Haiku, OpenAI and Gemini, routed by role, all reached through IBM ICA (one `.env` slot per family).

Read in this order before doing any work: `docs/PROGRESS.md` (where we are), then `docs/01-objectives.md`,
`docs/02-architecture.md`, `docs/03-agents-and-models.md`, `docs/05-build-plan.md`, `docs/06-testing-strategy.md`,
`docs/07-model-config.md`. `docs/00-analysis.md` and `docs/04-demo-scenario.md` are background.

## Working rules (apply to every session)

1. **One step at a time.** Work only on the step marked `IN PROGRESS` in `docs/PROGRESS.md`. Never start the next step until the user says go.
2. **Spec before code.** Copy `docs/steps/_TEMPLATE.md` to `docs/steps/Sxx-name.md`, fill it in, and get the user's OK before writing code for that step. Step specs are written just in time, not up front.
3. **Tests gate every step.** A step is done only when its listed tests pass and the full suite is still green (`pytest` from `backend/`). Report the real pass/fail output. Never mark a step done on a red or skipped suite without saying so.
4. **Do not run the app.** No servers, no Vite, no browser. Running `pytest` (and `vitest` for frontend logic) is fine and expected. When a step is done, hand the user a short manual-check list and let them test.
5. **Python venv:** `/Users/paragjain/dev-works/myenv`. It is shared with other lab apps, so do not upgrade or install SDKs into it. Only the dev dependencies named in the step spec (starting with pytest in S00) may be added.
6. **LLM access only through the gateway** (`backend/app/llm/`). Agents never call a provider directly. Unit tests never touch the network: they use the mock provider or `httpx.MockTransport`.
7. **Ports:** backend 8090, frontend 5270. Add a `start.sh` (FastAPI + frontend app convention) and, at the end, a card in `launcher/config.json`.
8. **Layout and style** follow sibling projects (`File-Compare` is the closest): `backend/app/`, pydantic-settings `config.py` reading `.env`, React + Vite + TypeScript frontend. Match the surrounding code's comment density and naming.
9. **Honest labelling.** Anything simulated (connectors, cloud deploy, incident) is labelled "simulated" in the UI and in docs. Never present a mock as a real integration.
10. **Confidentiality.** The source deck is confidential and this repo is public. Do not copy deck text, screenshots, logos or the product's name into code, UI, prompts or committed docs. (The `IBM_ICA_*` variable names and "ICA" as our LLM provider are fine: sibling lab apps already use them.) Do not commit the PDF. Never put client names in generated sample data. Do not read or print `.env` files.
11. **Commit only when asked.** Branch is `inflight-Work`.
12. **End of every step:** update `docs/PROGRESS.md`, and tell the user what to test and what to expect.
