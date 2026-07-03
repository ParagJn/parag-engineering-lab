import os
import glob
import json
from typing import List, Optional
from app.repositories.base_repo import BaseRepository
from app.models.workflow import WorkflowState

class WorkflowRepository:
    def __init__(self, data_dir: str):
        self.workflows_dir = os.path.join(data_dir, "workflows")
        if not os.path.exists(self.workflows_dir):
            os.makedirs(self.workflows_dir, exist_ok=True)

    def _get_file_path(self, workflow_id: str) -> str:
        # Sanitize workflow_id to avoid directory traversal
        safe_id = "".join([c for c in workflow_id if c.isalnum() or c in ("-", "_")])
        return os.path.join(self.workflows_dir, f"{safe_id}.json")

    def get(self, workflow_id: str) -> Optional[WorkflowState]:
        file_path = self._get_file_path(workflow_id)
        if not os.path.exists(file_path):
            return None
        
        repo = BaseRepository(file_path)
        data = repo.load()
        if not data:
            return None
        return WorkflowState(**data)

    def save(self, state: WorkflowState):
        file_path = self._get_file_path(state.workflow_id)
        repo = BaseRepository(file_path)
        repo.save(state.model_dump())

    def list_active(self) -> List[WorkflowState]:
        files = glob.glob(os.path.join(self.workflows_dir, "*.json"))
        res = []
        for f in files:
            try:
                with open(f, 'r') as fh:
                    data = json.load(fh)
                    res.append(WorkflowState(**data))
            except Exception:
                continue
        # Sort by creation / update or just return
        return res

    def delete(self, workflow_id: str):
        file_path = self._get_file_path(workflow_id)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
                
    def clear_all(self):
        files = glob.glob(os.path.join(self.workflows_dir, "*.json"))
        for f in files:
            try:
                os.remove(f)
            except OSError:
                pass
