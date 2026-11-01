"""Keeps tests away from the developer's real environment and real .env."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import app.config as config

# Everything Settings reads. Removed from os.environ before each test.
_PREFIXES = ("IBM_ICA_",)  # also covers IBM_ICA_OPENAI_API_KEY
_NAMES = (
    "APP_MODE", "RUN_BUDGET_USD", "LLM_TIMEOUT_SECONDS", "LLM_MAX_RETRIES",
    "LLM_RETRY_BACKOFF_SECONDS", "DATA_DIR", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "SSL_CERT_FILE",
    "REPLAY_SET", "RECORDINGS_DIR", "RECORD_LIVE_CALLS", "REPLAY_PACE",
    "CONTEXT_MAX_FILE_MB", "CONTEXT_MAX_PDF_PAGES", "CONTEXT_MAX_DOCS_PER_PROJECT", "CONTEXT_CHUNK_TARGET_CHARS",
    "AGENT_MAX_REPAIRS", "AGENT_MAX_OUTPUT_TOKENS", "AGENT_UPSTREAM_MAX_CHARS", "AGENT_CONTEXT_MAX_CHUNKS",
    "AGENT_CONTEXT_MAX_CHARS", "AGENT_CONTEXT_MIN_COVERAGE", "AGENT_TEMPERATURE", "AGENT_BRIEF_QUERIES",
)


def scrub(monkeypatch: pytest.MonkeyPatch, missing_env_file: Path) -> None:
    for name in list(os.environ):
        if name.startswith(_PREFIXES) or name in _NAMES:
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "ENV_FILE", missing_env_file)
    config.get_settings.cache_clear()
