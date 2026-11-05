"""Every setting a person may see or change, in groups, with plain words (S23d). Pure data and pure functions: no file, no database, no model.

The names, types and limits come from the app's own Settings class, so they cannot drift; this module adds only the WORDS (a label and a sentence), the GROUP, whether the value
is a SECRET, and whether it is shown at all. A test proves every field of Settings is here exactly once, so a new setting cannot be forgotten.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..config import Settings

KINDS = ("text", "number", "whole", "yes_no", "choice", "secret")


@dataclass(frozen=True)
class Setting:
    key: str                         # the field name in Settings, lower case; the variable in .env is the same name in upper case
    group: str
    label: str
    help: str
    kind: str                        # text | number | whole | yes_no | choice | secret
    secret: bool = False             # never shown, never echoed, never logged: only "set" or "not set"
    unit: str = ""
    choices: tuple[str, ...] = ()
    hidden: bool = False             # not offered on the screen at all (the file still holds it)

    @property
    def env_name(self) -> str:
        return self.key.upper()


GROUPS = (
    ("mode", "Mode and recordings", "Whether the app answers from recordings or calls real models, and where the recordings are."),
    ("connection", "Connection", "How the app reaches the models. The endpoint and the keys are secrets: they can be replaced here but are never shown."),
    ("sonnet", "Model: Sonnet", "The model used by reasoning roles (planning, requirements, architecture). Prices are USD per million tokens, used only for the cost estimate."),
    ("haiku", "Model: Haiku", "The model used by bulk and templated roles (backlog, diagrams, handover). Prices are USD per million tokens."),
    ("openai", "Model: OpenAI", "The model used by code and DevOps roles. Prices are USD per million tokens."),
    ("gemini", "Model: Gemini", "The model used by the UX designer and frontend roles. Prices are USD per million tokens."),
    ("budget", "Budget and limits", "How much a run may spend and how long it may take."),
    ("agents", "Writing and reviewing", "How much each agent and each review may write, and how many times a bad reply is repaired."),
    ("documents", "Documents", "The size limits for the documents a person uploads."),
    ("sandbox", "Sandbox and build", "The limits for running generated code, and how many fix rounds the Build phase gets."),
    ("people", "People", "The first person on the Users list."),
    ("advanced", "Advanced", "Rarely changed. Leave these alone unless you know why."),
)


def _s(key, group, label, help, kind, **kw) -> Setting:
    return Setting(key, group, label, help, kind, **kw)


def _slot(prefix: str, group: str, name: str) -> list[Setting]:
    return [
        _s(f"{prefix}_model_id", group, f"{name} model ID", "The model's ID exactly as the gateway names it. Blank falls back to the fallback model.", "text"),
        _s(f"{prefix}_fallback_model_id", group, f"{name} fallback model ID", "Used when the model above fails or is blank.", "text"),
        _s(f"{prefix}_price_input_per_mtok", group, f"{name} price in", "USD per million input tokens. Blank means cost shows as unknown, never zero.", "number", unit="USD / M tokens"),
        _s(f"{prefix}_price_output_per_mtok", group, f"{name} price out", "USD per million output tokens. Blank means cost shows as unknown, never zero.", "number", unit="USD / M tokens"),
    ]


SETTINGS: tuple[Setting, ...] = (
    _s("app_mode", "mode", "Mode", "Replay answers from recordings (free, offline). Live calls real models and costs money.", "choice", choices=("replay", "live")),
    _s("replay_set", "mode", "Recording set", "Which folder of recorded replies replay mode uses. Letters, digits, - and _ only.", "text"),
    _s("record_live_calls", "mode", "Record live calls", "In live mode, save every successful reply into the recording set so it can be replayed later. Recordings contain full prompts.", "yes_no"),
    _s("replay_pace", "mode", "Replay speed", "0 is instant; 1 waits as long as the original call took.", "number"),
    _s("recordings_dir", "mode", "Recordings folder", "Where recordings are kept. Blank means backend/recordings.", "text"),
    _s("ibm_ica_endpoint", "connection", "Gateway endpoint", "The address of the model gateway. A secret: shown only as set or not set.", "secret", secret=True),
    _s("ibm_ica_api_key", "connection", "API key", "The shared key for the gateway. A secret: shown only as set or not set.", "secret", secret=True),
    _s("ibm_ica_openai_api_key", "connection", "OpenAI key", "A separate key used only by models in the OpenAI slot. Blank uses the shared key.", "secret", secret=True),
    *_slot("ibm_ica", "sonnet", "Sonnet"),
    *_slot("ibm_ica_haiku", "haiku", "Haiku"),
    *_slot("ibm_ica_openai", "openai", "OpenAI"),
    *_slot("ibm_ica_gemini", "gemini", "Gemini"),
    _s("run_budget_usd", "budget", "Run budget", "The most one run may spend, in USD (an estimate from the prices). Used as the run cap unless the cap below is set too.", "number", unit="USD"),
    _s("run_max_cost_usd", "budget", "Run cost cap", "The hard stop for one run, in USD. 0 switches the cap off.", "number", unit="USD"),
    _s("run_max_seconds", "budget", "Run time cap", "The longest one run may take. 0 switches the cap off.", "number", unit="seconds"),
    _s("run_max_concurrency", "budget", "Artefacts written at once", "How many artefacts a run writes in parallel.", "whole"),
    _s("llm_timeout_seconds", "budget", "Model timeout", "How long to wait for one model call.", "number", unit="seconds"),
    _s("llm_max_retries", "budget", "Retries", "How many times a failed call is tried again on the same model before the fallback.", "whole"),
    _s("llm_retry_backoff_seconds", "budget", "Retry wait", "The wait before the first retry; it doubles each time.", "number", unit="seconds"),
    _s("agent_max_repairs", "agents", "Repairs per artefact", "How many times a reply that fails its checks is sent back to be fixed.", "whole"),
    _s("agent_max_output_tokens", "agents", "Output limit", "The most one agent call may write, unless its role has its own limit below.", "whole", unit="tokens"),
    _s("agent_output_tokens_by_role", "agents", "Output limit per role", "Roles that need more, as role=number pairs separated by commas, for example ux_designer=24000.", "text"),
    _s("agent_upstream_max_chars", "agents", "Input limit", "The most text from earlier artefacts one agent is shown.", "whole", unit="characters"),
    _s("agent_context_max_chunks", "agents", "Context pieces", "How many pieces of uploaded documents an agent may be shown.", "whole"),
    _s("agent_context_max_chars", "agents", "Context size", "The most uploaded-document text an agent may be shown.", "whole", unit="characters"),
    _s("agent_context_min_coverage", "agents", "Context match", "How well a piece of a document must match to be shown, from 0 to 1.", "number"),
    _s("agent_brief_queries", "agents", "Brief searches", "Extra searches of the documents, one per sentence of the brief.", "whole"),
    _s("review_max_output_tokens", "agents", "Review output limit", "The most one review may write.", "whole", unit="tokens"),
    _s("review_file_max_output_tokens", "agents", "Review output limit per file", "The most the review of ONE file of the Build instruction set may write.", "whole", unit="tokens"),
    _s("review_max_repairs", "agents", "Review repairs", "How many times a review that fails its checks is sent back.", "whole"),
    _s("review_max_findings", "agents", "Findings per review", "The most findings one review may list.", "whole"),
    _s("review_cited_max_chars", "agents", "Source text shown to a reviewer", "The most cited source text a reviewer is shown.", "whole", unit="characters"),
    _s("agent_temperature", "agents", "Temperature", "How varied the models' replies are, from 0 to 2. Blank leaves the model's own default.", "number"),
    _s("context_max_file_mb", "documents", "Largest file", "The largest document that can be uploaded.", "whole", unit="MB"),
    _s("context_max_pdf_pages", "documents", "Most PDF pages", "The most pages read from one PDF.", "whole"),
    _s("context_max_docs_per_project", "documents", "Documents per project", "The most documents one project may hold.", "whole"),
    _s("context_chunk_target_chars", "documents", "Piece size", "The size documents are cut into for searching.", "whole", unit="characters"),
    _s("sandbox_command_seconds", "sandbox", "Command time", "The longest one command may run in the sandbox.", "whole", unit="seconds"),
    _s("sandbox_test_seconds", "sandbox", "Test time", "The longest a test run may take.", "whole", unit="seconds"),
    _s("sandbox_output_bytes", "sandbox", "Output kept", "The most output kept from one command.", "whole", unit="bytes"),
    _s("sandbox_file_bytes", "sandbox", "Largest generated file", "The largest file the sandbox will write.", "whole", unit="bytes"),
    _s("sandbox_max_files", "sandbox", "Most generated files", "The most files one workspace may hold.", "whole"),
    _s("sandbox_total_bytes", "sandbox", "Workspace size", "The most total size of one workspace.", "whole", unit="bytes"),
    _s("sandbox_max_processes", "sandbox", "Most processes", "The most processes a command may start.", "whole"),
    _s("sandbox_memory_mb", "sandbox", "Memory", "The most memory a command may use.", "whole", unit="MB"),
    _s("build_fix_rounds", "sandbox", "Build fix rounds", "How many times the Build phase tries to fix failing code.", "whole"),
    _s("admin_name", "people", "First administrator", "Created with every role at start-up when the Users list is empty. A name is a label, not a password.", "text"),
    _s("guardrails_disabled_rules", "advanced", "Switched-off guardrail rules", "Rule names to switch off, separated by commas. Two rules cannot be switched off.", "text"),
    _s("run_event_queue", "advanced", "Event queue", "How many progress events are held for the screen.", "whole"),
    _s("run_heartbeat_seconds", "advanced", "Heartbeat", "How often the screen is told a run is still alive.", "number", unit="seconds"),
    _s("data_dir", "advanced", "Data folder", "Where the database lives. Blank means backend/data. Changing it points the app at a different database.", "text"),
    _s("ibm_ica_insecure_tls", "advanced", "Skip certificate checking", "Turns certificate checking OFF. For local connectivity testing only.", "yes_no"),
    _s("ibm_ica_user_agent", "advanced", "Client label", "The browser label sent to the gateway. A secret: shown only as set or not set.", "secret", secret=True),
)

BY_KEY = {s.key: s for s in SETTINGS}


def check_complete() -> list[str]:
    """Problems with the catalogue itself, in plain words: a setting the app has that is not here, one here the app does not have, a repeat, an unknown group or kind. Empty means sound."""
    problems: list[str] = []
    fields = set(Settings.model_fields)
    keys = [s.key for s in SETTINGS]
    problems += [f"{k} is a setting of the app but is not in the catalogue" for k in sorted(fields - set(keys))]
    problems += [f"{k} is in the catalogue but the app has no such setting" for k in sorted(set(keys) - fields)]
    problems += [f"{k} is listed twice" for k in sorted({k for k in keys if keys.count(k) > 1})]
    groups = {g for g, _, _ in GROUPS}
    problems += [f"{s.key} is in an unknown group {s.group!r}" for s in SETTINGS if s.group not in groups]
    problems += [f"{s.key} has an unknown kind {s.kind!r}" for s in SETTINGS if s.kind not in KINDS]
    problems += [f"{s.key} is a secret but its kind is {s.kind!r}" for s in SETTINGS if s.secret and s.kind != "secret"]
    problems += [f"{s.key} has kind 'secret' but is not marked secret" for s in SETTINGS if s.kind == "secret" and not s.secret]
    problems += [f"{s.key} is a choice with no choices" for s in SETTINGS if s.kind == "choice" and not s.choices]
    return problems
