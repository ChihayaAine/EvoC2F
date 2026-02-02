from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

from .events import TraceStore


class TraceExporter:
    def export_json(self, store: TraceStore, path: str) -> None:
        payload = [event.to_dict() for event in store.list()]
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def export_jsonl(self, store: TraceStore, path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            for event in store.list():
                handle.write(json.dumps(event.to_dict()) + "\n")

    def export_dict(self, store: TraceStore) -> Dict[str, Any]:
        return {
            "events": [event.to_dict() for event in store.list()],
            "count": store.size(),
        }

    def export_filtered(self, store: TraceStore, names: Iterable[str]) -> Dict[str, Any]:
        name_set = set(names)
        events = [event.to_dict() for event in store.list() if event.name in name_set]
        return {"events": events, "count": len(events)}

