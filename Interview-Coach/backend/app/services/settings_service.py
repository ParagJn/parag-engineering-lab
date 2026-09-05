import asyncio
import json
from pathlib import Path
from typing import Dict


class SettingsService:
    """Local JSON persistence for runtime AI provider settings."""

    DEFAULT_SETTINGS = {
        "provider_mode": "built_in",
        "api_keys": {
            "openai": "",
            "anthropic": "",
            "gemini": "",
        },
        "enabled_providers": [],
    }

    def __init__(self, settings_path: str):
        self.settings_path = Path(settings_path)
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def get_settings(self) -> Dict:
        async with self._lock:
            return self._read()

    async def update_settings(
        self,
        provider_mode: str,
        api_keys: Dict[str, str],
        enabled_providers: list,
    ) -> Dict:
        async with self._lock:
            current = self._read()
            current["provider_mode"] = provider_mode

            merged_keys = current.get("api_keys", {}).copy()
            for provider in ("openai", "anthropic", "gemini"):
                incoming = (api_keys.get(provider) or "").strip()
                if incoming:
                    merged_keys[provider] = incoming
            current["api_keys"] = merged_keys

            enabled = [
                provider
                for provider in enabled_providers
                if provider in ("openai", "anthropic", "gemini")
            ]
            if not enabled:
                enabled = [
                    provider
                    for provider in ("openai", "anthropic", "gemini")
                    if merged_keys.get(provider)
                ]
            current["enabled_providers"] = enabled

            if provider_mode == "custom":
                active = [
                    provider
                    for provider in enabled
                    if current["api_keys"].get(provider)
                ]
                if not active:
                    raise ValueError("Add and enable at least one API key for custom mode.")
                missing_enabled = [
                    provider
                    for provider in enabled
                    if not current["api_keys"].get(provider)
                ]
                if missing_enabled:
                    missing_labels = ", ".join(missing_enabled)
                    raise ValueError(f"Enabled providers need saved API keys: {missing_labels}")

            self._write(current)
            return current

    def to_public_settings(self, settings: Dict) -> Dict:
        keys = settings.get("api_keys", {})
        return {
            "provider_mode": settings.get("provider_mode", "built_in"),
            "has_keys": {
                "openai": bool(keys.get("openai")),
                "anthropic": bool(keys.get("anthropic")),
                "gemini": bool(keys.get("gemini")),
            },
            "masked_keys": {
                provider: self._mask_key(keys.get(provider, ""))
                for provider in ("openai", "anthropic", "gemini")
            },
            "enabled_providers": settings.get("enabled_providers", []),
        }

    def _read(self) -> Dict:
        if not self.settings_path.exists():
            return json.loads(json.dumps(self.DEFAULT_SETTINGS))

        with open(self.settings_path, "r", encoding="utf-8") as f:
            stored = json.load(f)

        settings = json.loads(json.dumps(self.DEFAULT_SETTINGS))
        settings.update({k: v for k, v in stored.items() if k != "api_keys"})
        settings["api_keys"].update(stored.get("api_keys", {}))
        if not settings.get("enabled_providers"):
            settings["enabled_providers"] = [
                provider
                for provider in ("openai", "anthropic", "gemini")
                if settings["api_keys"].get(provider)
            ]
        return settings

    def _write(self, settings: Dict) -> None:
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)

    def _mask_key(self, value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "****"
        return f"{value[:4]}****{value[-4:]}"
