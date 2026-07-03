import os
from typing import List
from app.repositories.base_repo import BaseRepository
from app.models.workflow import HistorySummary

class HistoryRepository:
    def __init__(self, data_dir: str):
        self.history_file = os.path.join(data_dir, "history.json")
        self.repo = BaseRepository(self.history_file, default_data=[])

    def get_all(self) -> List[HistorySummary]:
        data = self.repo.load()
        return [HistorySummary(**item) for item in data]

    def add(self, summary: HistorySummary):
        histories = self.repo.load()
        # Prevent duplicates
        histories = [h for h in histories if h.get("workflow_id") != summary.workflow_id]
        histories.append(summary.model_dump())
        self.repo.save(histories)

    def clear(self):
        self.repo.save([])
