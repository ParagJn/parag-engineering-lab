# S04 · Record and replay

**Milestone:** M1  **Size:** S–M  **Objectives:** O12, O13, O10  **Depends on:** S03

## Goal
Make the demo repeatable, free and offline. Two small wrappers around the provider interface from S02/S03:

- **Recording**: in live mode, save every *successful* model reply to disk as it happens.
- **Replay**: in replay mode, answer from those saved replies and never touch the network.

After this step `APP_MODE=replay` is a real mode with a real provider instead of "unwired", and the M1 milestone (foundations) is complete.

## In scope
- `llm/providers/recording.py`: `RecordingProvider` (wraps a real provider) and `ReplayProvider`, sharing one `RecordingStore`.
- `llm/recordings.py`: the request key, the on-disk format, loading, atomic saving, and a report of anything unusable.
- A typed `ReplayMiss` error and the matching gateway rule.
- Settings: `REPLAY_SET`, `RECORDINGS_DIR`, `RECORD_LIVE_CALLS`, `REPLAY_PACE`.
- Provider selection in `create_app`, a `recordings` block in `/api/status`, one line on the page.
- `scripts/replay_check.py`: a script you run that proves the record → replay round trip against the real service.
- Recordings folder gitignored for now (see decision 4).

## Out of scope (later steps)
- Recording failures, so a run that went through a fallback can't be replayed (see "What this does not do").
- Falling back to a live call when a recording is missing.
- Editing recordings in the UI, checkpoints and reset (S23), the committed demo set (S24).
- Streaming and tool calls (none exist yet).

## Design

### What identifies a recording
A recording is looked up by a SHA-256 over a canonical JSON of:

| Part of the key | Why |
|---|---|
| **model ID** | The reply came from that model. Routing to another model is a miss, not a wrong answer |
| **system prompt** and every **message** (role + text, in order) | The actual question |
| **max_tokens**, **temperature** | They change what the model returns. A truncated reply must not be served for a bigger limit |

**Not in the key:** the agent role, project id, phase and run id. Those differ on every demo reset, and a replay that broke when a project got a new id would be useless. The role is still stored in the file for people to read. The key is sorted-key JSON with no whitespace differences, so it is stable across machines and Python versions, and a message list is order-sensitive (it is a conversation).

### On disk
One small JSON file per recording at `backend/recordings/<REPLAY_SET>/<first 16 hex of key>.json`: one file per entry, so git diffs are readable and a parallel run never contends on a single file.
```
{ "format": 1, "key": "<64 hex>", "model": "...", "role": "...", "recorded_at": "...Z",
  "latency_ms": 1234,
  "request":  { "system": "...", "messages": [{"role","content"}], "max_tokens": 4096, "temperature": null },
  "response": { "text": "...", "usage": {"tokens_in": n, "tokens_out": n} | null, "finish_reason": "stop" } }
```
- Writes are atomic (temp file in the same folder, then rename), so a crash never leaves a half-written file and two writers of the same key leave one intact file. The last write wins when a key is recorded again.
- **Only successful replies are recorded.** Errors, blocks and empty replies are not.
- **Fail closed on secrets:** if the request or the reply contains any configured secret (either API key, the endpoint, the user-agent), that entry is **not saved**, a warning is logged without the value, and the live call itself is unaffected.
- A recording whose stored key doesn't match its stored request (someone edited the prompt text) is **reported and skipped**. Editing the *response* text is allowed, since that is how a recording gets scrubbed.

### Replay
- Loads the whole set once, at startup (a dict; reads are thread-safe).
- A hit returns the recorded text, usage and finish reason. The gateway then computes cost from the recorded token counts at **today's** configured prices, writes its normal trace, and labels the family from the model, exactly as in a live run. So the cost and trace views (O10) show real token counts in replay.
- **A miss is strict.** `ReplayMiss` is raised, with: the role, the model, a short key, how many recordings exist for that model, and how to record it. It is **not retried and does not fall back**: falling back to another model would only miss again, or, worse, hit a recording made for a different model and make the demo look like it worked. A miss in the reviewer path also fails with the message instead of offering the family picker, since the other families would miss too.
- **Pacing:** `REPLAY_PACE` is the fraction of the recorded latency to wait before answering. `0` (default) is instant. `0.25` makes a 4 s call take 1 s, so parallel agents are visibly "working" in the demo instead of finishing together. The recorded latency is capped at 60 s, and the sleep is injectable for tests. Nothing about pacing is hidden: the page says REPLAY.

### Recording
- `RecordingProvider(inner, store)` calls the real provider, and on success saves the entry under the **model that was actually called**, then returns the reply unchanged. A save failure is logged and never breaks the call (same rule as trace writes).
- It is switched on by `APP_MODE=live` **and** `RECORD_LIVE_CALLS=true`. Saves run off the event loop.

### Selecting the provider
| Mode | Credentials | `RECORD_LIVE_CALLS` | Provider |
|---|---|---|---|
| `replay` | not needed | ignored (the page lists it as a problem if set) | `ReplayProvider` over the set |
| `live` | endpoint + key set | off | `IcaProvider` |
| `live` | endpoint + key set | on | `RecordingProvider(IcaProvider)` |
| `live` | missing | any | unwired, as before |

### Settings (defaults need no `.env` edit)
`REPLAY_SET` (default `demo`; letters, digits, `-` and `_` only, so a value can't point outside the recordings folder), `RECORDINGS_DIR` (default `backend/recordings`), `RECORD_LIVE_CALLS` (default off), `REPLAY_PACE` (0 to 1, default 0).

### `/api/status` and the page
New `gateway.recordings`: `mode` (`replay`, `recording`, `off`), `set`, `count`, and `problems` (file name + reason, never content). Problems also join the gateway problem list in replay mode. A set with **zero** recordings is *not* a problem: a fresh checkout has none until a set is recorded, and a permanently red page would teach you to ignore it. The page shows "Recordings: 12 in set 'demo'" (or "recording to 'demo'").

### The round-trip script (you run it, I do not)
`cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.replay_check`
1. Makes the same four tiny calls as the live check, through a `RecordingProvider`, into a **temporary** folder.
2. Builds a `ReplayProvider` on that folder and repeats the calls with **no network provider in the process**.
3. Prints, per slot: recorded vs replayed latency, same text (yes/no), same tokens (yes/no), same cost (yes/no).
4. Makes one deliberate miss and prints the miss message, so you see exactly what a stale recording looks like.
5. Ends `4/4 round trips identical`; exit code 1 otherwise. Never prints replies, keys, the endpoint or the user-agent, and deletes the temp folder.
Costs the same fraction of a cent as the live check. It proves our file format survives a *real* ICA reply, which fake-network tests cannot.

## What this does not do (known limits)
- **A run that used a fallback can't be replayed.** If OpenAI failed live and Sonnet answered, only the Sonnet entry exists, so replay asks OpenAI first and misses. Record the demo set from a run where all four slots work (they do now).
- **Any change to a prompt is a miss.** Editing a skill, a schema or a model ID invalidates the recordings it touched. Expect to re-record after prompt changes; that is the price of replay being exact.
- **Prompts are stored in full**, so a recording can contain whatever was typed into the brief or uploaded. The secret check above only covers *our* credentials. The recordings folder stays gitignored until S24, where the committed demo set gets an explicit content check for client names (project rule 10).
- Two calls with an identical key but different live answers collapse to the latest one.

## Tests (must pass before the step is done)
All offline. Recording and replay are tested against a scripted inner provider; the existing fake-network helpers cover the ICA path.

| Area | Proves |
|---|---|
| key | stable across calls; identical for equal requests; changes with model, system, any message text or order, max_tokens, temperature; **unchanged by role, project, phase, run id**; unicode and long text; no collisions on near-miss prompts |
| format | round trip of text, usage, finish reason, role, model; usage `None` survives; file name is the key prefix; one file per entry; valid JSON; `format` field present |
| atomic save | no temp files left behind; a failed write leaves the previous file intact; 20 concurrent saves of different keys all land; 20 of the same key leave one valid file |
| recording | the reply is returned unchanged; saved under the model actually called (including a fallback model); errors are passed through and **not** recorded; a save failure is logged and the reply still returned; saves happen off the event loop |
| secrets | a reply, a prompt, a system prompt containing the key, the OpenAI key, the endpoint or the user-agent: that entry is **not written**, a warning is logged, the warning does not contain the value, the live reply is still returned |
| replay hit | text, usage, finish reason as recorded; through the gateway: cost from recorded tokens at **current** prices, a normal `ok` trace, family labelled, `attempts == 1` |
| replay miss | `ReplayMiss`; message has role, model, short key, count for that model and the recording hint; not retried; no fallback tried (the mock proves the fallback model was never asked); trace written as `replay_miss`; reviewer path raises `LLMCallFailed`, not `ReviewerUnavailable` |
| near miss | same prompt on another model, one changed character, different max_tokens: all misses |
| loading | empty or missing set is fine (count 0, no problem); corrupt JSON, wrong `format`, missing fields, key that doesn't match the stored request: skipped and **reported by file name without content**; the good files still load; an edited response still loads |
| pacing | `0` never sleeps; `0.25` sleeps a quarter of the recorded latency; capped at 60 s; `None` latency treated as 0; invalid values rejected by settings |
| settings | defaults; bounds; set name rejects `../x`, `a/b`, empty, spaces, over-long; accepted names; read from a `.env` file |
| selection | the four rows of the selection table; `RECORD_LIVE_CALLS` ignored in replay and listed as a problem; replay mode needs no credentials |
| status | `recordings` block shape for each mode; count matches files; problems named; zero recordings is not a problem; no paths or content in the response |
| end to end | record through the real gateway with a scripted provider, build a fresh app in replay mode on the same folder, repeat the calls: identical text, tokens and cost, **zero provider calls** (the scripted provider is replaced by one that fails the test if touched) |
| replay_check script | rows built from results; "identical" only when text, tokens and cost all match; a mismatch is reported and exits 1; the deliberate miss message is printed; **output never contains replies, keys, endpoint or user-agent**; temp folder removed; refuses to run without credentials |

After the suite is green I'll run the same break-one-thing check as for S01–S03 (key ignores the model, key includes the project id, miss falls back, error replies recorded, secrets saved, non-atomic write, edited prompt accepted, cost taken from recorded dollars instead of recomputed, `../` accepted in the set name, pacing ignored, and so on) and confirm each break is caught.

## Dependencies / installs
None. Standard library only.

## Decisions for you (defaults chosen; say if you want any changed)
1. **Strict replay.** A miss fails with a clear message and never falls back or goes live. Alternative: on a miss, make a live call and record it, which is friendlier while developing but means a replay demo can quietly spend money or fail on stage when the network is down. I'd keep replay strict and use live mode with recording for development.
2. **Pacing setting, default instant.** For the real demo I'd try `REPLAY_PACE=0.25`.
3. **The key includes `max_tokens` and `temperature`.** More misses after tuning, but never a stale or truncated answer served for a different setting.
4. **Recordings are gitignored until S24.** Prompts are stored in full, so I don't want them committed by accident. At S24 the demo set gets a deliberate scrub and a content check.

## Manual check for the user (we do not run the app)
1. Run the round trip yourself (costs a fraction of a cent):
   `! cd /Users/paragjain/dev-works/parag-engineering-lab/SDLC-Workbench/backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.replay_check`
   Expect `4/4 round trips identical`, replay latency in single-digit milliseconds, and a printed miss message. Paste the output back to me.
2. `./start.sh`, open `http://localhost:5270`. With `APP_MODE=replay` the page should show the **REPLAY** pill, `Provider: replay`, and **Recordings: 0 in set 'demo'**, with the Gateway pill still green.
3. Optional: set `RECORD_LIVE_CALLS=true` while in replay mode, reload, and the Gateway pill should turn red with a problem naming that variable. Remove it afterwards.
   (Note the pill: on the page the recordings pill only appears in replay or recording mode, and reads "Recordings: 0 in set 'demo'".)
4. Nothing on the page calls a model yet, so the recording count stays 0 until a later step.

## Decisions taken (user, 2026-10-27)
All four defaults accepted: strict replay; pacing setting defaulting to instant; key includes `max_tokens` and `temperature`; recordings gitignored until S24.

## Done when
- [x] Listed tests pass; full suite green (`493 passed, 1 deselected`, in PROGRESS.md)
- [x] Break-one-thing check run and reported (37 of 37 caught)
- [x] Frontend `npm run build` still succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] Round-trip script run by the user and its result recorded: 4/4 identical (2026-10-27). Live latency was unusually high in that run (sonnet 158 s); noted in PROGRESS.md
- [x] Closed on the 4/4 result, as agreed in the previous message
