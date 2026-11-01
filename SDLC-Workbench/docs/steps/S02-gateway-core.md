# S02 · LLM gateway core

**Milestone:** M1  **Size:** M  **Objectives:** O2, O3 (changed, see below), O10, O13  **Depends on:** S00, S01

## Goal
One door for every model call. An agent says *who it is* (a role) and *what it wants*; the gateway picks the model, handles failure, prices the call and writes a trace. After this step everything runs against a **mock provider**; the real ICA client arrives in S03 and record/replay in S04.

## Decisions taken (user, 2026-10-27)
| # | Decision | Effect |
|---|---|---|
| 1 | **Sonnet reviews every artefact.** | Reviews of Sonnet- and Haiku-authored work are *same family*. O3 therefore changes from "the reviewer is always a different family" to "every review is labelled **independent** or **same family**, never hidden". Independent only for OpenAI- and Gemini-authored work. |
| 2 | One retry, backoff 1s then 2s | `LLM_MAX_RETRIES=1`, `LLM_RETRY_BACKOFF_SECONDS=1` |
| 3 | **When a reviewer is unavailable, the user chooses the model family.** | A review call never falls back by itself. If it fails, the gateway raises `ReviewerUnavailable` carrying the usable options with family, independence and price. The picker UI comes with the review screen (S08/S12). Non-review calls still fall back automatically to the slot's fallback (Sonnet) as decided in D10. |
| 4 | Per-attempt traces, schema v2 | One trace row per attempt, `call_id` groups them |
| 5 | Gateway pill and routing table on the page | As below |

## In scope
- Types, the async `Provider` contract and typed provider errors.
- Routing: role → slot from `routing.yaml`, optional per-project overrides, blank-slot handling.
- Model families, the reviewer default, **review options** and the **independence verdict**.
- Pricing and cost by the model that actually served the call.
- Retry, timeout and fallback policy; `Gateway.review()` with the ask-the-user path.
- One trace row per attempt (migration v2). A migration runner that is safe when two processes start together.
- Mock provider for tests; an "unwired" provider so the app starts today.
- Config checks and a `gateway` block in `/api/status`, shown on the page.

## Out of scope (later steps)
- HTTP to ICA and its error mapping (S03). Record/replay provider (S04).
- Prompts, skills, output schemas (S07). Running a review and acting on it, and the picker UI (S08, S12).
- Budget cap and progress events (S09). Streaming, JSON mode, tool calls.
- Haiku's long-prompt price tier and Gemini's date-based price rises (noted in `07-model-config.md`).

## Design

### Files (`backend/app/llm/`)
```
errors.py   types.py   families.py   pricing.py   routing.py   routing.yaml
gateway.py  status.py  providers/{base,mock,unwired}.py
```

### Contract
```python
LLMRequest(role, messages, system="", max_tokens=4096, temperature=None,
           project_id=None, phase_key=None, run_id=None)       # LLMRequest.user(role, text, **kw)
ProviderResponse(text, usage: Usage | None, finish_reason)     # Usage(tokens_in, tokens_out)
class Provider:  async complete(model_id, request) -> ProviderResponse
LLMResult(text, call_id, role, slot, requested_model, served_model, family, fallback_used,
          attempts, tokens_in, tokens_out, latency_ms, cost_usd, finish_reason, trace_ids)

Gateway.complete(request, *, slot=None, overrides=None, allow_fallback=True) -> LLMResult
Gateway.review(request, *, author_model, slot=None, exclude=()) -> ReviewOutcome
Gateway.review_options(author_model, *, exclude=()) -> [ReviewerOption]
Gateway.independence(author_model, result) -> Independence
```
`slot=` forces a slot; otherwise `overrides` (a project's `routing_overrides`, `{role: slot}`) beats `routing.yaml`. When a slot is forced, `role` is just the trace label.

### Slots, families, prices
- Slot → family is fixed: sonnet, haiku → `anthropic`; openai → `openai`; gemini → `google`. A **model ID** gets its family from the slot that owns it, else from its prefix (`claude`; `gpt`, `chatgpt`, `o<digit>`; `gemini`), else `unknown`.
- Price is looked up by **served model ID** through the slot that owns it, so a call that fell back to Sonnet is priced at Sonnet's rates. A model owned by no slot, a blank price, or a call with no usage report gives cost `None` (unknown, never 0).
- `cost = tokens_in × price_in / 1e6 + tokens_out × price_out / 1e6`. Zero tokens at a known price is `0.0`.
- Two slots with the same model ID but different prices are a **config problem** (listed in `/api/status`, naming the env variables).

### Routing and the reviewer
`routing.yaml` holds the 14 role → slot rows from `03-agents-and-models.md` plus the reviewer:
```yaml
reviewer:
  default: sonnet
  alternatives: [gemini, openai, haiku]   # order in which options are offered
```
- A bad `routing.yaml` (unknown slot or role, missing role, bad reviewer section) is a code defect: `create_app` raises `RoutingConfigError` with a message that names the problem.
- **Review options** (`review_options`): every slot that has its own model ID, minus excluded slots and any slot sharing an excluded slot's model. Each option carries slot, model, family, `independent` (true / false / null when a family is unknown) and its prices. Independent options are listed first, then unknown, then same family; within a group the `alternatives` order holds.
- **Independence** (`independence`): `independent`, `same_family` or `unverified`, from the author's **served** model family against the reviewer's served model family. The author's family comes from the model that actually wrote the artefact, so OpenAI work that fell back to Sonnet counts as Sonnet-authored.
- **`review()`**: calls the default reviewer slot (or the one the user chose) with `allow_fallback=False`. Retries on the *same* model still happen. If the slot has no model, or the call fails in a way another model might fix (timeout, rate limit, 5xx, content filter), it raises `ReviewerUnavailable(slot, options)`. The caller shows the options, the user picks, and the caller calls `review(slot=chosen, exclude=…)` again. Auth and bad-request failures raise `LLMCallFailed` as usual because another model would fail the same way.
- A **blank slot** on a normal call uses the slot's fallback and is marked `fallback_used`. With no fallback either, `SlotNotConfigured` is raised **before** any provider call or trace.

### Failure policy (one `complete()` call)
| Provider signal | Retry same model | Then fall back | Why |
|---|---|---|---|
| Timeout, 429, 5xx | yes, up to `LLM_MAX_RETRIES`, with backoff | yes (unless `allow_fallback=False`) | Transient |
| Content-filter block | no | yes (same) | Same prompt on the same model blocks again |
| Auth (401/403) | no | **no** | One key serves every model, so the fallback fails identically. Message names `IBM_ICA_API_KEY` and `IBM_ICA_ENDPOINT`, not their values |
| Bad request (400/422) | no | **no** | Our bug, not luck |
| Any other exception | no | no | Recorded as an error trace, then re-raised unchanged |
| Cancellation | no | no | Always propagates; no trace is written for the cancelled attempt |

- A fallback is tried **only if it is a different model** from the primary. The Sonnet slot's fallback is itself, so a Sonnet failure is retried and then fails: exactly `1 + LLM_MAX_RETRIES` attempts.
- Each attempt is wrapped in `LLM_TIMEOUT_SECONDS`. Expiry counts as a timeout.
- Backoff is `LLM_RETRY_BACKOFF_SECONDS × 2^(n−1)`, capped at 10s, slept only between retries of the same model, with an injectable sleep.
- Total failure raises `LLMCallFailed`, carrying every attempt.
- Error text is passed through a redaction step that strips the API key and the endpoint before it reaches a trace or an exception.

### Traces
- **One row per attempt.** Failed attempts: status `error`, 0 tokens, cost `None`. Columns: agent = role, slot, `requested_model` (the slot's own model, or `"(not set)"`), `served_model`, `fallback_used`, tokens, latency, cost, project, phase, run, and the new `call_id` and `attempt`.
- **Migration v2** adds `call_id TEXT` and `attempt INTEGER NOT NULL DEFAULT 1`. Existing rows keep working. The schema becomes **v2**, so the page pill changes from "v1" to "v2".
- **Traces never contain prompts or responses.** Error text is cut to 500 characters.
- Trace writes run in a worker thread. **If a trace write fails, the model's answer is still returned** and a warning is logged; `trace_ids` is then empty.
- Because v2 uses `ALTER TABLE`, the migration runner now re-checks the schema version *after* taking the write lock and runs statements one by one, so two processes starting together cannot apply a step twice.

### Config additions (defaults in code, no `.env` edit needed)
`LLM_MAX_RETRIES` (default 1, 0–5), `LLM_RETRY_BACKOFF_SECONDS` (default 1.0, 0–30). `LLM_TIMEOUT_SECONDS` becomes a positive number (tests use fractions). Documented in `.env.example`.

### Providers in this step
- **MockProvider**: scripted outcomes per model ID (a response, an error to raise, or a hang), records every request, optional barrier to prove calls overlap, deterministic usage estimate.
- **UnwiredProvider**: raises "no provider is wired yet". `create_app` uses it so the app starts; nothing in the running app calls a model yet.

### `/api/status` and the page
New `gateway` block: `config_ok`, `provider`, `problems` (plain sentences naming **env variable names**, never values), `routing` (14 rows: role, slot, model, `using_fallback`) and `reviewer` (default slot, its model, alternatives). In `replay` mode only structure problems count. In `live` mode a missing endpoint, a missing key, or a slot with neither model nor fallback is also a problem. The page gets a "Gateway config" pill, a problems list and a routing table.

## Tests (must pass before the step is done)

| Area | Proves |
|---|---|
| families | slot→family; prefix inference; slot ownership beats prefix; `unknown` stays unknown |
| pricing | served model priced by its owning slot; **Sonnet-fallback call priced at Sonnet rates**; unowned model or blank price → `None`; 1000/200 at 2/10 = 0.004; zero tokens = `0.0`; half-priced → `None`; duplicate model IDs with different prices flagged |
| routing file | shipped `routing.yaml` valid; all 14 roles; **every slot is the default for at least one role** (O2); reviewer default is Sonnet; unknown slot/role, missing role, bad shapes and missing file rejected with a clear message |
| overrides | project override beats the file; unknown role or slot rejected; none leaves the file's choice; a forced slot beats both |
| review options | independent first; excluded and blank-model slots dropped; slots sharing the failed model dropped; unknown author family → `independent: None`; prices and family included |
| independence | OpenAI/Gemini author → independent; **Sonnet and Haiku author → same family**; unknown → unverified; family comes from the **served** model; `fell_back` reported |
| `review()` | Sonnet reviews by default; user-chosen slot honoured; **no automatic fallback** (an OpenAI reviewer that fails does not silently become Sonnet); transient/content-filter failure and a blank reviewer slot → `ReviewerUnavailable` with options; auth failure stays `LLMCallFailed`; `exclude` carries over between rounds |
| happy path | result fields correct; one `ok` trace with every column, `call_id`, attempt 1 |
| usage | provider reports none → tokens 0, cost `None`, counted unpriced in rollups |
| retry | transient error retried then succeeds; attempts and trace rows right; backoff 1,2,… capped at 10; `LLM_MAX_RETRIES=0` means one attempt |
| fallback | retries exhausted → fallback serves; trace rows N errors then one `ok` with `fallback_used`; `requested_model` is the primary; shared `call_id`; fallback's rates; fallback also failing → `LLMCallFailed` listing every attempt |
| content filter | no same-model retry; falls back at once; fails after one attempt on the Sonnet slot |
| auth / bad request | one attempt, no fallback, error trace; the secret is redacted from the trace and the exception |
| Sonnet slot | transient failures: exactly `1 + retries` attempts, never `fallback_used` |
| blank slot | blank model → fallback, `fallback_used`, `requested_model == "(not set)"`; no fallback either → `SlotNotConfigured`, **no provider call, no trace** |
| timeout / cancel / bug | a hang is cut off at `LLM_TIMEOUT_SECONDS` and retried; `CancelledError` propagates with no trace and no retry; an unexpected exception is traced and re-raised unchanged |
| trace failure | with `traces.record` broken the result is still returned and a warning is logged |
| concurrency | 5 calls are **inside the provider at once** (barrier: a serial gateway would hang and fail); unique `call_id`s and trace ids |
| leak guard | prompt and response sentinels appear **nowhere in the database file** (with a control check that the method can find a planted value) |
| migration | fresh DB is v2 with the new columns; a v1 file with data migrates and keeps its rows; **concurrent migrate calls on a fresh file all succeed** |
| mock provider | script consumed in order; records requests; exhausted script gives a clear error |
| config | retry and backoff bounds; timeout must be positive; defaults apply with nothing in `.env` |
| status | `gateway` block shape; replay is OK with no keys; live with nothing set is not, and `problems` name env variables and contain **no secret values**; 14 routing rows; duplicate-model problem; reviewer block |

After the suite is green I'll break about a dozen guarantees one at a time in a scratch copy (same-model fallback, auth falling back, pricing by requested model, unknown cost as 0, swallowed cancellation, unprotected trace write, retry off by one, review auto-fallback, option ordering, independence always true, migration re-check, redaction) and confirm the suite fails each time.

## Dependencies / installs
None. Standard library plus PyYAML, already in the venv.

## Manual check for the user (we do not run the app)
1. `./start.sh`, open `http://localhost:5270`.
2. The page shows **Gateway config: OK**, and the Database pill says **v2**.
3. A **Routing** table lists 14 roles, for example `requirements_analyst → Sonnet → claude-sonnet-5-5`, `backend_developer → OpenAI → gpt-5.6-sol`, `ux_designer → Gemini → gemini-3.7-flash`, `backlog_splitter → Haiku → claude-haiku-5-5`. A line shows the reviewer: Sonnet (`claude-sonnet-5-5`).
4. Optional: in `.env` set `APP_MODE=live` and blank both `IBM_ICA_HAIKU_MODEL_ID` and `IBM_ICA_HAIKU_FALLBACK_MODEL_ID`, reload, and the pill turns red with a problem naming those two variables. **Put both back afterwards.**
5. Nothing calls a model in this step, so no cost is incurred.

## Done when
- [x] Listed tests pass; full suite green (`242 passed, 1 deselected`, in PROGRESS.md)
- [x] Mutation check run and reported (20 of 20 caught)
- [x] Frontend `npm run build` still succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] User confirmed 2026-10-27 ("good so far"; the page was not re-screenshotted)
