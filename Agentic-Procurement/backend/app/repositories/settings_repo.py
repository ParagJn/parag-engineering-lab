import os
from app.repositories.base_repo import BaseRepository
from app.models.settings import Settings

DEFAULT_SETTINGS = {
    "gemini_key": "",
    "claude_key": "",
    "buyer_model": "gemini-1.5-flash",
    "supplier_model": "claude-3-5-sonnet-20240620"
}

class SettingsRepository:
    def __init__(self, data_dir: str):
        self.settings_file = os.path.join(data_dir, "settings.json")
        self.repo = BaseRepository(self.settings_file, default_data=DEFAULT_SETTINGS)

    def load_settings(self) -> Settings:
        data = self.repo.load()
        # Merge keys in case fields are missing from legacy saves
        merged = DEFAULT_SETTINGS.copy()
        merged.update(data)
        return Settings(**merged)

    def save_settings(self, settings: Settings):
        self.repo.save(settings.model_dump())
