"""What the settings are right now, as the screen needs them (S23d). Reads the app's own loaded Settings; never reads or prints the .env file itself.

A secret is only ever "set" or "not set". Its value is not in the answer, not in an error and not in a log. Every other setting is shown as the app holds it, with its default beside it
so a person can see what they changed.
"""
from __future__ import annotations

from typing import Any

from ..config import Settings
from .catalogue import BY_KEY, GROUPS, SETTINGS, Setting



def _raw(settings: Settings, key: str) -> Any:
    return getattr(settings, key)


def is_set(settings: Settings, setting: Setting) -> bool:
    """A secret counts as set when it holds something other than blanks."""
    value = _raw(settings, setting.key)
    text = value.get_secret_value() if hasattr(value, "get_secret_value") else str(value or "")
    return bool(text.strip())


def shown(value: Any) -> str:
    """A value as text for the screen: blank for nothing, 'true' / 'false' for yes and no."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _defaults() -> dict[str, str]:
    """The app's own defaults, read from the field definitions: nothing from any file and nothing from the environment (a Settings() built even with no file still reads the environment)."""
    return {name: shown(field.get_default(call_default_factory=True)) for name, field in Settings.model_fields.items()}


DEFAULTS = _defaults()


def entry(settings: Settings, setting: Setting) -> dict[str, Any]:
    out: dict[str, Any] = {
        "key": setting.key, "env_name": setting.env_name, "group": setting.group, "label": setting.label, "help": setting.help, "kind": setting.kind,
        "unit": setting.unit, "choices": list(setting.choices), "secret": setting.secret,
    }
    if setting.secret:
        out["is_set"] = is_set(settings, setting)                       # the value is never put in the answer
    else:
        out["value"] = shown(_raw(settings, setting.key))
        out["default"] = DEFAULTS[setting.key]
        out["changed"] = out["value"] != out["default"]
    return out


def describe(settings: Settings, *, pending: bool = False, can_edit: bool = False) -> dict[str, Any]:
    """Everything the Settings tab needs: the groups in order, each with its settings. `pending` says a saved change is waiting for a restart."""
    return {
        "groups": [
            {"key": key, "title": title, "help": help_, "settings": [entry(settings, s) for s in SETTINGS if s.group == key and not s.hidden]}
            for key, title, help_ in GROUPS
        ],
        "restart_pending": pending,
        "can_edit": can_edit,
        "note": "These are read from backend/.env when the app starts. Secrets are never shown: only whether they are set.",
    }


def known(key: str) -> Setting | None:
    return BY_KEY.get(key)
