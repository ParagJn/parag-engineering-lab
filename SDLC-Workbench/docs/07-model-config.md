# 07 · Model configuration and price reference

## How models are configured

All four families are reached through ICA (decision D1) with one shared `IBM_ICA_ENDPOINT` and `IBM_ICA_API_KEY`. **Exception (user, 2026-10-27): GPT models use `IBM_ICA_OPENAI_API_KEY` when it is set** (the shared key was denied access to the GPT model). The key is chosen by the model that serves the call: a GPT request that falls back to Sonnet is sent with the shared key, so the OpenAI key never reaches a Claude model. `backend/.env` holds one **slot** per family: `sonnet`, `haiku`, `openai`, `gemini`. Each slot has a model ID and a fallback model ID. ICA treats all models the same way (D6, per the user), so there are no per-slot endpoint or key overrides. Agent roles map to slots in the routing config (`03-agents-and-models.md`), so changing a model is an `.env` edit and changing which role uses which slot is a routing edit. Neither touches Python.

Rules the gateway enforces from this config:
- A blank slot means its roles use the slot's fallback, and the UI flags it. If the fallback is blank too, the run refuses to start in live mode with a message naming the slot.
- Review independence (O3) is computed from the model that actually *served* the author's call and the one that served the review, not from slot names. Sonnet reviews everything by default; a review is labelled independent or same family.
- `APP_MODE=replay` needs no keys at all.
- Keys are never logged, never returned by the API, and never appear in `repr(settings)` (tested in S00).

## Prices

Cost is an **estimate**. Prices are config parameters in `backend/.env`, two per slot: `IBM_ICA_<SLOT>_PRICE_INPUT_PER_MTOK` and `..._OUTPUT_PER_MTOK` (the Sonnet slot has no slot name: `IBM_ICA_PRICE_INPUT_PER_MTOK`). USD per million tokens. A blank price shows cost as "unknown" instead of zero, and per-model rollups say how many calls were unpriced. The gateway prices each call by the model that actually served it, so a call that fell back to Sonnet is priced at the Sonnet slot's rates, not the original slot's. Changing a price is an `.env` edit; no Python or YAML.

The reference tables below were read from the providers' public pricing pages on **2026-10-27**, USD per million tokens, standard tier, short-context rates. The OpenAI figures came through a page summariser, so verify them. ICA may bill differently from list price; put ICA's rates in `.env` if so.

Limits of single-rate config: Haiku 5.5 costs more for prompts over 100k tokens, and a few Gemini rows change price on 2026-12-01 and 2027-01-01. One input and one output price per slot can't express either, so the estimate will undercount long Haiku prompts and go stale after those dates. Cached-input discounts are also ignored. Prompts in this prototype are mostly well under 100k, so this is acceptable. If it matters, a later step can add optional tier and date variables.

### Anthropic (Sonnet and Haiku slots)

| Model | Input | Cache hit | Output | Notes |
|---|---|---|---|---|
| Claude Sonnet 5.5 | 2.00 | 0.10 | 10.00 | |
| Claude Sonnet 5 | 2.00 | 0.20 | 10.00 | |
| Claude Haiku 5.5, prompt ≤100k | 0.10 | 0.01 | 0.50 | |
| Claude Haiku 5.5, prompt >100k | 0.50 | 0.05 | 2.50 | Long-context rate; the meter must switch on prompt size |
| Claude Haiku 4.5 | 1.00 | 0.10 | 5.00 | |

### OpenAI (code roles)

| Model | Input | Cached | Output |
|---|---|---|---|
| gpt-5.3-codex | 1.75 | 0.175 | 14.00 |
| gpt-6.1-sol | 2.00 | 0.10 | 10.00 |
| gpt-6.1-terra | 1.00 | 0.05 | 5.00 |
| gpt-5.4-mini | 0.75 | 0.075 | 4.50 |
| gpt-5.5 | 5.00 | 0.50 | 30.00 |

### Gemini (UX and frontend roles)

| Model | Input | Output | Notes |
|---|---|---|---|
| gemini-3.1-pro-preview | 2.00 | 12.00 | |
| gemini-3.8-flash | 0.75 | 3.75 | Rises to 1.50 / 7.50 from 2027-01-01 |
| gemini-3.6-flash | 0.75 | 3.75 | Rises to 1.50 / 7.50 from 2027-01-01 |
| gemini-3.5-flash-lite | 0.30 | 2.50 | |
| gemini-2.5-pro | 1.25 | 10.00 | |
| gemini-4-argon | 2.00 | 10.00 | Rises to 4.00 / 20.00 from 2026-12-01 |

These are reference candidates only. **You choose the model IDs** and keep the matching prices in `.env`.

## Rough run cost (for budget sizing, not a promise)

A full seven-phase run is on the order of a few hundred thousand tokens in and a bit over a hundred thousand out, mostly in Build & Test. At the prices above that lands in the low single dollars with mid-range model choices, which is why `RUN_BUDGET_USD` defaults to 5.00. S22 replaces this guess with measured numbers.

## What to fill in

Nothing is outstanding: the endpoint, key, all four model IDs and all four prices are set. Recheck the Gemini and OpenAI prices when you can. You never need to paste keys to me.

## Current slot assignments (2026-10-27)

| Slot | Model ID (`.env` variable) | Fallback | Price in / out per MTok |
|---|---|---|---|
| Sonnet | `claude-sonnet-5-5` (`IBM_ICA_MODEL_ID`) | `claude-sonnet-5-5` | 2.00 / 10.00 |
| Haiku | `claude-haiku-5-5` (`IBM_ICA_HAIKU_MODEL_ID`) | `claude-sonnet-5-5` | 0.10 / 0.50 (prompts ≤100k) |
| OpenAI | `gpt-6.1-sol` (`IBM_ICA_OPENAI_MODEL_ID`; was `gpt-5.6-sol`, which the shared key was denied) | `claude-sonnet-5-5` | 2.00 / 10.00. The user chose this on 2026-10-28 (the old `.env` value 4.00 / 20.00 was the `gpt-5.6-sol` price). The figure comes from a pricing page read by a summariser, not from ICA, so it is still unconfirmed against ICA's own rate. Uses its own key (`IBM_ICA_OPENAI_API_KEY`). Live check 4/4 on 2026-10-27 |
| Gemini | `gemini-3.7-flash` (`IBM_ICA_GEMINI_MODEL_ID`) | `claude-sonnet-5-5` | 0.75 / 3.75, filled in by the user. `gemini-3.7-flash` itself isn't on the pricing page I read; these match the 3.6 and 3.8 flash list price, which rises to 1.50 / 7.50 on 2027-01-01 |

Sonnet is the default fallback for every slot (user decision). Consequences to remember:
- The Sonnet slot's fallback is itself. A fallback is only tried when it is a *different* model from the one that just failed, so a Sonnet failure is retried on Sonnet (the retry count in `.env`, default 1) and then fails the call. A content-filter block on Sonnet fails at once, because retrying the same model would be blocked again. Details in `docs/steps/S02-gateway-core.md`.
- A reviewer never falls back on its own. If it can't run, the gateway raises `ReviewerUnavailable` with the other model families (independent ones first, with their prices) and the user chooses. Ordinary non-review calls still fall back to Sonnet automatically.

The variable names follow the lab's existing convention. One endpoint serves all four slots. One key serves Sonnet, Haiku and Gemini; GPT models can have their own (`IBM_ICA_OPENAI_API_KEY`). There are no other per-slot endpoint or key overrides.
