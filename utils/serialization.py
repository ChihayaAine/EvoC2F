from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional


class JsonSerializer:
    def __init__(self, indent: int = 2, ensure_ascii: bool = True, sort_keys: bool = True) -> None:
        self.indent = indent
        self.ensure_ascii = ensure_ascii
        self.sort_keys = sort_keys

    def dumps(self, payload: Dict[str, Any]) -> str:
        return json.dumps(
            self._normalize(payload),
            indent=self.indent,
            ensure_ascii=self.ensure_ascii,
            sort_keys=self.sort_keys,
        )

    def loads(self, payload: str) -> Dict[str, Any]:
        return json.loads(payload)

    def dump_file(self, payload: Dict[str, Any], path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.dumps(payload))

    def load_file(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as handle:
            return self.loads(handle.read())

    def _normalize(self, payload: Any) -> Any:
        if is_dataclass(payload):
            return asdict(payload)
        if isinstance(payload, dict):
            return {k: self._normalize(v) for k, v in payload.items()}
        if isinstance(payload, (list, tuple)):
            return [self._normalize(v) for v in payload]
        return payload

