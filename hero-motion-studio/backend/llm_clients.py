from __future__ import annotations

import asyncio
from dataclasses import dataclass

from config import Settings
from ibm_ica_client import IBMICAClient, IBMICAError


class ProviderError(RuntimeError):
    pass


@dataclass
class AgentResult:
    agent: str
    content: str
    ok: bool = True


class IcaCompletionAgent:
    def __init__(self, settings: Settings, name: str, model: str):
        self.settings = settings
        self.name = name
        self.model = model

    @property
    def configured(self) -> bool:
        return bool(self.settings.ibm_ica_endpoint and self.settings.ibm_ica_api_key)

    async def complete(self, system: str, user: str, max_tokens: int = 4000) -> AgentResult:
        if not self.configured:
            raise ProviderError("IBM ICA is not configured")

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        print(
            f"[IBM_ICA] agent={self.name!r} model={self.model!r} "
            f"endpoint={self.settings.ibm_ica_endpoint!r}",
            flush=True,
        )
        client = IBMICAClient(
            endpoint=self.settings.ibm_ica_endpoint,
            api_key=self.settings.ibm_ica_api_key,
            model_id=self.model,
        )
        try:
            result = await asyncio.to_thread(client.chat, messages, max_tokens)
        except IBMICAError as err:
            print(f"[IBM_ICA] agent={self.name!r} FAILED: {err!r}", flush=True)
            raise ProviderError(f"IBM ICA error: {err}") from err
        return AgentResult(agent=f"{self.name} ({self.model})", content=result["text"].strip())


def build_agent(settings: Settings, name: str, kind: str = "claude") -> IcaCompletionAgent:
    """Build an IBM ICA agent. `kind` selects the model: "claude" or "gemini"."""
    model = settings.ibm_ica_model_id if kind == "claude" else settings.ibm_ica_gemini_model_id
    return IcaCompletionAgent(settings, name, model)
