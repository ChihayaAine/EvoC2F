from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, Optional


class JsonStore:
    def __init__(self, path: str) -> None:
        self.path = path

    def load(self) -> Dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            return {}

    def save(self, payload: Dict[str, Any]) -> None:
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix="store-", suffix=".json", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        os.replace(tmp_path, self.path)

    def update(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        payload = self.load()
        payload.update(patch)
        self.save(payload)
        return payload

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return self.load().get(key, default)

    def delete(self, key: str) -> Dict[str, Any]:
        payload = self.load()
        if key in payload:
            payload.pop(key)
            self.save(payload)
        return payload

    def exists(self) -> bool:
        return os.path.exists(self.path)

