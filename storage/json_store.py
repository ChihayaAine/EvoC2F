from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class StoreConfig:
    indent: int = 2
    sort_keys: bool = True
    ensure_ascii: bool = True
    retry_attempts: int = 3
    retry_backoff_s: float = 0.05
    lock_timeout_s: float = 2.0
    backup_suffix: str = ".bak"


class JsonStore:
    def __init__(self, path: str, config: Optional[StoreConfig] = None) -> None:
        self.path = path
        self.config = config or StoreConfig()
        self._lock = threading.Lock()

    def load(self) -> Dict[str, Any]:
        with self._lock:
            return self._load_with_retries()

    def save(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._save_atomic(payload)

    def update(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            payload = self._load_with_retries()
            payload.update(patch)
            self._save_atomic(payload)
            return payload

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        return self.load().get(key, default)

    def set(self, key: str, value: Any) -> Dict[str, Any]:
        return self.update({key: value})

    def delete(self, key: str) -> Dict[str, Any]:
        with self._lock:
            payload = self._load_with_retries()
            if key in payload:
                payload.pop(key)
                self._save_atomic(payload)
            return payload

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def list_keys(self) -> Tuple[str, ...]:
        payload = self.load()
        return tuple(sorted(payload.keys()))

    def load_or_init(self, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.exists():
            return self.load()
        payload = default or {}
        self.save(payload)
        return payload

    def backup(self) -> Optional[str]:
        if not self.exists():
            return None
        backup_path = f"{self.path}{self.config.backup_suffix}"
        with open(self.path, "rb") as src, open(backup_path, "wb") as dst:
            dst.write(src.read())
        return backup_path

    def _load_with_retries(self) -> Dict[str, Any]:
        attempts = 0
        while True:
            try:
                with open(self.path, "r", encoding="utf-8") as handle:
                    return json.load(handle)
            except FileNotFoundError:
                return {}
            except json.JSONDecodeError:
                attempts += 1
                if attempts >= self.config.retry_attempts:
                    self.backup()
                    return {}
                time.sleep(self.config.retry_backoff_s * attempts)

    def _save_atomic(self, payload: Dict[str, Any]) -> None:
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix="store-", suffix=".json", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                payload,
                handle,
                indent=self.config.indent,
                sort_keys=self.config.sort_keys,
                ensure_ascii=self.config.ensure_ascii,
            )
        os.replace(tmp_path, self.path)

