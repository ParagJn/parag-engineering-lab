# S03 · ICA provider adapter

**Milestone:** M1  **Size:** S–M  **Objectives:** O2, O13  **Depends on:** S02

## Goal
The first code that talks to the real service. An `IcaProvider` plugs into the S02 gateway, turns an `LLMRequest` into an ICA chat-completions call for any of the four model slots, and turns every outcome into the typed errors the gateway already knows how to retry, fall back on, or refuse. Alongside it, a **live-check script that you run yourself** makes one tiny call per slot and tells us what ICA actually does with Sonnet, Haiku, OpenAI and Gemini.

**Honest limit of this step:** all automated tests use a fake transport. They prove our code handles each response shape correctly. They cannot prove ICA sends those shapes. Section "What is still unverified" lists what only your first live run can settle, and the script exists to settle it.

## What we copy from the sibling apps (already works for you)
Read from `File-Compare/backend/app/ibm_ica_client.py` (the same client Daily-Articles and Strategy-Analyzer use):
- `POST {endpoint}/v1/chat/completions`, `Authorization: Bearer <key>`, JSON body `{model, messages, max_tokens}`.
- System prompt as a `{"role": "system"}` first message (OpenAI style).
- Reply text at `choices[0].message.content` (a string, or a list of `{text}` parts); also accepts `content[0].text`.
- `finish_reason == "content_filter"` on a 200 means the reply was blocked.
- 401/403 mean bad credentials; the TLS context is built from `certifi`, with an opt-in switch to turn verification off.
- A browser-style `User-Agent` header (see decision 2).

## In scope
- `llm/providers/ica.py`: `IcaProvider` over `httpx.AsyncClient` (one pooled client, closed on app shutdown).
- Two new typed errors plus one for TLS, and the matching one-line gateway change.
- Settings: `IBM_ICA_INSECURE_TLS` (default off), `IBM_ICA_USER_AGENT` (default: the sibling value).
- Wiring: `create_app` uses `IcaProvider` when `APP_MODE=live` and endpoint and key are set.
- `scripts/live_check.py` and a small shape-describing helper.
- `httpx` and `certifi` added to `requirements.txt` (both already installed in your venv).

## Out of scope (later steps)
- Record/replay (S04). Prompts and schemas (S07). Budget cap (S09).
- Streaming, tool calls, JSON mode, image input.
- Honouring a `Retry-After` header (a 429 is retried by the gateway's own backoff).
- A per-family request tweak. You said ICA treats all models the same; the live check will confirm, and if it doesn't, the fix is small and comes with its own test.

## Design

### Request
- URL: `endpoint` stripped of whitespace and trailing `/`; `/v1/chat/completions` is appended unless the endpoint already ends with it. An endpoint ending in `/v1` gets `/chat/completions`.
- Body: `model`, `messages` (system first if present, then user/assistant turns in order), `max_tokens`. `temperature` is sent **only** when the request sets it. Never `stream`.
- Headers: `Authorization: Bearer …`, `Content-Type`/`Accept: application/json`, `User-Agent`.
- Timeouts: read/write/pool = `LLM_TIMEOUT_SECONDS`, connect = 10 s. (The gateway also wraps each attempt in the same limit.)
- Pool: shared client, up to 20 connections, so a phase running six agents in parallel never queues on the pool.
- TLS: `certifi` bundle by default. `IBM_ICA_INSECURE_TLS=true` turns verification off, and `/api/status` then lists it as a problem in live mode so it cannot be left on unnoticed.

### Response
- Text from `choices[0].message.content` (string or list of `{text}` parts), else `content[0].text`.
- Usage from `usage`: `prompt_tokens`/`completion_tokens`, or `input_tokens`/`output_tokens`. If absent or not whole numbers → `None` (the gateway then records cost as unknown, never a guess).
- `finish_reason` passed through.
- **Empty or whitespace-only text is an error** (`BadResponse`), with the finish reason in the message. Reasoning models can spend the whole `max_tokens` budget thinking and return nothing; the message says so ("raise max_tokens").

### Error mapping
| What ICA does | Raised | Gateway then |
|---|---|---|
| 200 with `finish_reason: content_filter` | `ContentFilterBlocked` | fall back at once |
| 400 whose error code/message mentions a content filter | `ContentFilterBlocked` | fall back at once |
| 401, 403 | `AuthenticationFailed` | fail, names `IBM_ICA_API_KEY`/`IBM_ICA_ENDPOINT` |
| 400, 422, other 4xx | `BadRequest` | fail, no fallback (our bug) |
| **404** (or an error saying the model does not exist) | **`ModelNotFound`** (new) | no same-model retry, **fall back to Sonnet** |
| 408, 429, 500, 502, 503, 504, 529 | `TransientProviderError` | retry, then fall back |
| connect error, DNS, read/connect timeout, dropped connection | `TransientProviderError` | retry, then fall back |
| certificate verification failed | **`TlsVerificationFailed`** (new) | fail at once; message points at `certifi` / `IBM_ICA_INSECURE_TLS` |
| 200 but not JSON, or no usable reply, or empty text | **`BadResponse`** (new) | no same-model retry, fall back |

- Why 404 falls back: your model IDs (`gpt-5.6-sol`, `gemini-3.7-flash`) have not yet been seen by ICA from this app. If one is not available, falling back keeps the demo alive instead of crashing, and the live check reports it clearly.
- Error text is built only from the parsed `error.message` / `error.code` fields, capped at 300 characters. The **raw response body is never included**, so an error that echoes a prompt cannot leak into a trace. (If a provider's own `message` quotes the prompt, that sentence would still be recorded; the 300-character cap limits it.)
- The key and endpoint never appear in any raised error (the gateway also redacts them as a second layer).

### Gateway change (small)
`LLMCallFailed.retryable_elsewhere` also counts `model_not_found` and `bad_response` (another model could fix them), and `TlsVerificationFailed` joins auth and bad-request as "fail at once, no fallback". Because `review()` uses `retryable_elsewhere`, a reviewer whose model is not found now asks you to pick another family, as designed.

### Wiring
- `APP_MODE=live` and endpoint and key set → `IcaProvider`; otherwise the unwired provider (so `replay` stays unwired until S04). Building the provider makes no network call.
- The provider label shown on the page becomes `ica`. The HTTP client closes when the app shuts down.

### The live-check script (you run it, I do not)
`cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.live_check` (optionally `--slot openai`, `--shape`).
- Reads your real `.env`, uses a throwaway database (your real one is untouched), and goes through the real gateway with **fallback switched off**, so a broken slot is reported as broken instead of being hidden by Sonnet.
- One call per slot: *"Reply with the single word: ready"*, `max_tokens` 200. About 4 × (30 tokens in, a few out): well under one cent at your prices.
- Prints a table: slot, model, family, `ok`/failure kind, finish reason, tokens in/out, latency, cost (or `unknown`), and for failures the cleaned message. Ends with `N/4 slots OK` and exits 1 if any failed.
- `--shape` additionally prints the **names** of the keys in each response (never values), so if usage or text isn't where we expect we learn exactly where it is.
- Never prints the key, the endpoint or the user-agent. Refuses to run if the endpoint or key is missing and says which variable.

## What is still unverified (only the live check settles it)
1. Whether ICA's OpenAI and Gemini models answer in the same chat-completions shape as Claude (you said they do).
2. The names of the usage fields for each family. If missing, cost shows "unknown", which is safe but unhelpful.
3. How ICA reports a content-filter block (200 + `finish_reason`, or a 400).
4. What a missing model looks like (404, or 400 with a message).
5. Whether the `gpt-5.x` and `gemini-3.x` models accept `max_tokens`, or insist on a different parameter name. Some newer OpenAI models do, and a gateway may or may not translate it.
6. Whether these models return an empty reply at a small `max_tokens` because they "think" first. That is why the script uses 200, and why empty replies are errors with a hint.
7. Whether the gateway requires the browser-style User-Agent.
8. The real rate limits when six agents run at once (S09 territory).

## Tests (must pass before the step is done)
All use `httpx.MockTransport`. None touches the network.

| Area | Proves |
|---|---|
| URL building | bare host; trailing slash; whitespace; already ends `/v1/chat/completions`; ends `/v1` |
| wire request | method, URL, `Authorization: Bearer <key>`, JSON content type, user-agent; body has `model`, `max_tokens`, no `stream`; `temperature` only when set |
| messages | system first; user/assistant order kept; no system → no system message |
| parsing | string content; content-part list; `content[0].text` shape; surrounding whitespace trimmed |
| usage | `prompt_tokens`/`completion_tokens`; `input_tokens`/`output_tokens`; missing → `None`; non-integer or negative → `None`; booleans rejected |
| finish reason | `stop`, `length` passed through; `content_filter` → `ContentFilterBlocked` |
| empty reply | `""`, whitespace, `null` → `BadResponse` naming the finish reason; `length` adds the "raise max_tokens" hint |
| bad 200s | non-JSON body; JSON without `choices`; `choices: []` → `BadResponse` |
| status mapping | every row of the table above, parametrised, including a 400 whose body mentions a content filter and a 400 saying the model does not exist |
| connection failures | `ConnectError`, `ConnectTimeout`, `ReadTimeout`, `RemoteProtocolError` → transient; certificate failure → `TlsVerificationFailed` |
| error text | built from `error.message`/`code` only; capped at 300; raw body, key and endpoint never present, even when the server echoes them; non-JSON error body gives only the status |
| client | one shared client across calls; `aclose()` closes it; closed again safely; app shutdown closes it; timeout and pool limits applied |
| TLS setting | default verifies against certifi; `IBM_ICA_INSECURE_TLS=true` disables; status lists it as a problem in live mode only |
| settings | new settings default correctly and read from a `.env` file; user-agent override works |
| construction | no network on build; blank endpoint or key → clear config error naming the variable |
| wiring | live + credentials → provider label `ica`; live without credentials → unwired; replay → unwired |
| gateway integration | over the fake transport: OpenAI model 404 → falls back to Sonnet, trace shows `model_not_found` then `ok`, cost at Sonnet's rates; 401 → one attempt, no fallback, secret absent from trace and exception; TLS failure → one attempt; empty reply → falls back; 503 then 200 → retried on the same model; cost computed from parsed usage end to end |
| reviewer | a reviewer whose model is not found raises `ReviewerUnavailable` with options |
| concurrency | 6 calls in flight at once through the real provider and fake transport (barrier) |
| live-check script | table rows built from results; failures show kind and cleaned message; exit code 0 only when all slots pass; `--slot` filter; fallback disabled; uses a temp database; **output never contains key, endpoint or user-agent**; refuses to run with a missing key; `--shape` prints key names only |
| describe-shape | nested dict → key names; values never included; lists summarised |

After the suite is green I'll run the same break-one-thing check as in S01 and S02 (404 treated as bad request, usage keys swapped, raw body leaked into errors, temperature always sent, content filter ignored, empty text accepted, TLS failure retried, client recreated per call, redaction removed, and so on) and confirm each break is caught.

## Dependencies / installs
None to install. `httpx` 0.28.1 and `certifi` are already in your venv; I'll list them in `requirements.txt` so a fresh machine gets them.

## Decisions for you (defaults chosen; say if you want any changed)
1. **A missing model (404) falls back to Sonnet** rather than failing. Alternative: fail loudly so a wrong model name can't hide behind Sonnet. My view: fall back, but the live check and the page should make a silent fallback easy to spot, and the traces already record it.
2. **User-Agent.** Your sibling apps all send a browser-style one, probably because the gateway or a firewall in front of it rejects default Python agents. I'll send the same string by default and make it a setting. If you'd rather send an honest `SDLC-Workbench/0.1` and see whether ICA accepts it, say so; the live check will tell us.
3. **Live check design:** four tiny calls, fallback off, temporary database, run by you. Alternative: a "Test connection" button on the page. I'd keep that for later; a script gives clearer output now.
4. **Empty replies are errors**, not empty successes. A review or artefact with no text is never useful, and treating it as success would let it flow downstream.
5. **Replay mode stays unwired** until S04.

## Manual check for the user
I will **not** run the live check: it needs your key, costs real money (cents), and sits outside the "tests never touch the network" rule. Run it yourself:
1. `! cd /Users/paragjain/dev-works/parag-engineering-lab/SDLC-Workbench/backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.live_check`
2. Expect a four-row table and `4/4 slots OK`. Paste the table back to me, whatever it says. A failing row is useful information, not a problem with the step.
3. If any row shows an empty reply, a 400, or missing usage, run it again with `--shape` and paste that too. It prints key names only, no content.
4. Optional: set `APP_MODE=live` in `.env`, restart, and the page's routing section should say `Provider: ica`. Set it back to `replay` afterwards if you don't want live behaviour.

## Decisions taken (user, 2026-10-27)
All five defaults accepted: 404 falls back to Sonnet; browser-style User-Agent by default (a setting); live check is a script, button later; empty replies are errors; replay stays unwired until S04. "Sonnet is the default for everything" was confirmed for the earlier fallback question.

## What the first live run settled (2026-10-27)
| Unverified item | Result |
|---|---|
| 1. Do OpenAI and Gemini answer in the same shape as Claude? | Gemini yes. **OpenAI not yet seen**: the model was denied before any reply |
| 2. Usage field names per family | Sonnet, Haiku, Gemini all reported usage in the fields we read; cost matched the configured prices |
| 3. How a content filter is signalled | Not seen |
| 4. What a missing model looks like | **A 403 with code `team_model_access_denied`, not a 404.** Handled as `model_access_denied` after the run exposed the bug |
| 5. Does `max_tokens` work on the newer models? | Yes for Gemini. OpenAI not yet seen |
| 6. Empty replies at small token limits | None at `max_tokens` 200. Gemini used 101 output tokens for one word, so it does spend tokens on something. Watch this in S09 when parallel agents add up cost |
| 7. Is the browser-style User-Agent needed? | Not tested. It worked, and we left it in |
| 8. Real rate limits | Not tested |

## Done when
- [x] Listed tests pass; full suite green (`367 passed, 1 deselected`, in PROGRESS.md)
- [x] Break-one-thing check run and reported (35 of 35 caught)
- [x] Frontend `npm run build` still succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] Live check run by the user and its result recorded (3 of 4 slots OK)
- [x] OpenAI slot working: second live check 4/4 (2026-10-27), after the user added `IBM_ICA_OPENAI_API_KEY` and changed the OpenAI model to `gpt-6.1-sol`
- [x] Closed by me on the 4/4 result, as agreed in the previous message. The OpenAI price question is tracked in PROGRESS.md
