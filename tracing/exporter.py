from __future__ import annotations

import json
from typing import Any, Dict

from .events import TraceStore


class TraceExporter:
    def export_json(self, store: TraceStore, path: str) -> None:
        payload = [
            {"name": event.name, "timestamp": event.timestamp, "payload": event.payload}
            for event in store.list()
        ]
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def export_dict(self, store: TraceStore) -> Dict[str, Any]:
        return {
            "events": [
                {"name": event.name, "timestamp": event.timestamp, "payload": event.payload}
                for event in store.list()
            ],
            "count": store.size(),
        }

