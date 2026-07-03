import os
import json
import threading
from typing import Any, Dict, Optional

# Global lock to prevent concurrent write issues
_repo_lock = threading.Lock()

class BaseRepository:
    def __init__(self, file_path: str, default_data: Any = None):
        self.file_path = file_path
        self.default_data = default_data if default_data is not None else {}
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        with _repo_lock:
            if not os.path.exists(self.file_path):
                with open(self.file_path, 'w') as f:
                    json.dump(self.default_data, f, indent=4)

    def load(self) -> Any:
        with _repo_lock:
            if not os.path.exists(self.file_path):
                return self.default_data
            try:
                with open(self.file_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return self.default_data

    def save(self, data: Any):
        with _repo_lock:
            directory = os.path.dirname(self.file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            with open(self.file_path, 'w') as f:
                json.dump(data, f, indent=4)
