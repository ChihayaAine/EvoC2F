from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class TraceEvent:
    name: str
    timestamp: float
    payload: Dict[str, Any] = field(default_factory=dict)
    level: str = "info"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "level": self.level,
        }


class TraceStore:
    def __init__(self, capacity: Optional[int] = None) -> None:
        self._events: List[TraceEvent] = []
        self._capacity = capacity

    def emit(
        self,
        name: str,
        payload: Optional[Dict[str, Any]] = None,
        level: str = "info",
    ) -> None:
        self._events.append(
            TraceEvent(name=name, timestamp=time.time(), payload=payload or {}, level=level)
        )
        if self._capacity and len(self._events) > self._capacity:
            overflow = len(self._events) - self._capacity
            self._events = self._events[overflow:]

    def list(self) -> List[TraceEvent]:
        return list(self._events)

    def filter(self, name: str) -> List[TraceEvent]:
        return [event for event in self._events if event.name == name]

    def filter_level(self, level: str) -> List[TraceEvent]:
        return [event for event in self._events if event.level == level]

    def filter_prefix(self, prefix: str) -> List[TraceEvent]:
        return [event for event in self._events if event.name.startswith(prefix)]

    def export(self) -> List[Dict[str, Any]]:
        return [event.to_dict() for event in self._events]

    def since(self, timestamp: float) -> List[TraceEvent]:
        return [event for event in self._events if event.timestamp >= timestamp]

    def between(self, start_ts: float, end_ts: float) -> List[TraceEvent]:
        return [event for event in self._events if start_ts <= event.timestamp <= end_ts]

    def summary(self) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        for event in self._events:
            counts[event.name] = counts.get(event.name, 0) + 1
        return {"count": len(self._events), "by_name": counts}

    def clear(self) -> None:
        self._events.clear()

    def size(self) -> int:
        return len(self._events)

