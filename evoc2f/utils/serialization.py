from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict


class JsonSerializer:
    def dumps(self, payload: Dict[str, Any]) -> str:
        return json.dumps(self._normalize(payload), indent=2, ensure_ascii=True)

    def loads(self, payload: str) -> Dict[str, Any]:
        return json.loads(payload)

    def _normalize(self, payload: Any) -> Any:
        if is_dataclass(payload):
            return asdict(payload)
        if isinstance(payload, dict):
            return {k: self._normalize(v) for k, v in payload.items()}
        if isinstance(payload, (list, tuple)):
            return [self._normalize(v) for v in payload]
        return payload

