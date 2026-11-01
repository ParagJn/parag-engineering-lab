from __future__ import annotations

from ..config import Settings
from .families import family_of_model

SHARED_KEY_VARIABLE = "IBM_ICA_API_KEY"
OPENAI_KEY_VARIABLE = "IBM_ICA_OPENAI_API_KEY"


def _uses_openai_key(settings: Settings, model_id: str) -> bool:
    """GPT models, whichever slot asked for them, when an OpenAI key is set."""
    return settings.openai_key_is_own and family_of_model(model_id, settings.slots) == "openai"


def api_key_for_model(settings: Settings, model_id: str) -> str:
    """The key to send for a call served by this model.

    Chosen by the model that answers, not by the slot that asked, so a GPT request that falls
    back to Sonnet is sent with the shared key and the OpenAI key never reaches a Claude model.
    """
    if _uses_openai_key(settings, model_id):
        return settings.ibm_ica_openai_api_key.get_secret_value().strip()
    return settings.ibm_ica_api_key.get_secret_value().strip()


def key_variable_for_model(settings: Settings, model_id: str) -> str:
    """The .env variable holding the key that api_key_for_model returns. For error messages."""
    return OPENAI_KEY_VARIABLE if _uses_openai_key(settings, model_id) else SHARED_KEY_VARIABLE
