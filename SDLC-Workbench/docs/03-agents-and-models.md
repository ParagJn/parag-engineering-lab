# 03 · Agents, skills and model routing

## Principles

1. **Route by job, not by loyalty.** Cheap and fast models for structured, bounded work; stronger models where reasoning or code quality matters.
2. **Sonnet reviews; independence is labelled, not forced.** *(Changed 2026-10-27 at the user's request; the original rule was "reviewer family ≠ author family".)* Sonnet reviews every artefact. A review of OpenAI- or Gemini-authored work is **independent**; a review of Sonnet- or Haiku-authored work is **same family** and is shown that way. If the reviewer can't run, the review pauses and the user picks another family from the offered options; it never changes model on its own.
3. **Agents are data.** An agent is: a role name, a skill file, a model assignment, an output schema, and a list of allowed tools. No per-agent Python class.
4. **Everything routed through config.** Defaults below are a starting point. We tune them after seeing real outputs and cost, and the demo can show "swap the model, rerun, compare".

"Sonnet", "Haiku", "OpenAI" and "Gemini" below are **slots**. Each slot's actual model ID, fallback and per-million-token prices come from `backend/.env` (see `07-model-config.md`), and all four are reached through ICA.

## Default routing (to be tuned in S02 and S16)

| Role | Phase | Output | Default model | Reason |
|---|---|---|---|---|
| Orchestrator / planner | all | phase plan, task split, summaries | Sonnet | Reasoning over the whole project |
| Requirements analyst | 1 | personas, problem statements, vision, FR/NFR, epics | Sonnet | Long-form structured writing |
| Backlog splitter | 1 | epics → features → stories (bulk, templated) | Haiku | Cheap, high-volume, schema-bound |
| UX designer | 2 | user journey, low-fi + hi-fi wireframes (as HTML/SVG) | Gemini | Strong at layout and visual markup |
| Solution architect | 3 | component overview, flows, use-case diagram, HLD, LLD | Sonnet | Trade-offs and consistency |
| Diagram author | 3 | Mermaid / SVG from the architecture | Haiku | Mechanical rendering |
| Database engineer | 4 | schema, migrations, seed data | Haiku | Bounded, verifiable by running it |
| Backend developer | 4 | API code | OpenAI | Code generation |
| Frontend developer | 4 | HTML/JS UI | Gemini | UI code generation |
| Test engineer | 4 | unit and API tests | OpenAI | Test generation; verified by execution |
| DevOps engineer | 5 | Dockerfile, compose, Terraform, pipeline, deploy script | OpenAI | Config and scripting |
| Security reviewer | 4–5 | findings on code, IaC, artefacts | Sonnet | Careful reading; additive to the deterministic scanner |
| Handover author | 6 | runbook, SLOs/alerts, KT pack, support guide | Haiku | Templated from approved artefacts |
| Incident triage | 6 | classify the simulated incident, propose fix | Sonnet | Reasoning over logs |
| **Reviewer (per artefact)** | all | findings, severity, pass/fail | Sonnet | Default reviewer for everything (`reviewer.default` in `routing.yaml`). Alternatives offered to the user when it is unavailable: Gemini, OpenAI, Haiku, independent families first |

Coverage check for O2: Sonnet, Haiku, OpenAI and Gemini all appear as authors above, so a normal run uses all four.

## Skills

A skill is a Markdown file under `backend/app/phases/skills/`. Fixed sections so they can be linted:

```
# Skill: <name>
## Role            who the agent is, one paragraph
## Inputs          upstream artefact types and context queries it should run
## Output          artefact type, output schema reference, ID prefix, required sections
## Method          numbered steps the agent follows
## Quality bar     checklist the reviewer also uses
## Never           things it must not do (invent names of real clients, skip IDs, etc.)
```

Skills are editable in the UI later (O11). A skill linter test fails if a required section is missing.

## Agent loop (S07)

1. Resolve inputs: upstream approved artefacts + context retrieval + project memory (past reviewer feedback).
2. Build the prompt from the skill plus the retrieved chunks, each tagged with its source ID.
3. Call the gateway with the output schema. Parse and validate. On invalid output, retry up to N times with the validation error appended.
4. Save as a new artefact version with `author`, cited source IDs, token and cost.
5. Reviewer agent (other family) produces findings. Findings are stored on the version, not silently applied.
6. Phase moves to `awaiting_review`. The human approves, edits, or rejects with feedback. A rejection re-runs only the affected artefacts with the feedback in context.

Tool-using agents (developers, test engineer, DevOps) add a bounded tool loop: write file → run tests → read failures → fix, with a hard cap on iterations and tokens.

## Failure behaviour (must be tested)

| Failure | Behaviour |
|---|---|
| Provider timeout, 429 or 5xx | Retry with backoff (`LLM_MAX_RETRIES`, default 1), then fall back to the slot's fallback model if it is a different model. Every attempt is a trace row |
| Content-filter block | No same-model retry; go to the fallback model at once (the lab's existing clients do this). On the Sonnet slot, whose fallback is itself, it fails |
| Auth error (401/403) or bad request (400/422) | Fail at once with no retry and no fallback: a fallback uses the same key, and a bad request is our bug |
| Invalid structured output | Retry with the validation error; after N, mark artefact `failed` with the reason |
| Budget cap hit | Stop the run, keep partial work, show why |
| Blank model ID or missing key for a slot | That slot's roles use its fallback model, flagged in the UI. If the fallback is blank too, a live run refuses to start and names the slot. Replay mode never needs keys |
