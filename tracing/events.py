from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TraceEvent:
    name: str
    timestamp: float
    payload: Dict[str, Any] = field(default_factory=dict)


class TraceStore:
    def __init__(self) -> None:
        self._events: List[TraceEvent] = []

    def emit(self, name: str, payload: Optional[Dict[str, Any]] = None) -> None:
        self._events.append(
            TraceEvent(name=name, timestamp=time.time(), payload=payload or {})
        )

    def list(self) -> List[TraceEvent]:
        return list(self._events)

    def filter(self, name: str) -> List[TraceEvent]:
        return [event for event in self._events if event.name == name]

    def since(self, timestamp: float) -> List[TraceEvent]:
        return [event for event in self._events if event.timestamp >= timestamp]

    def clear(self) -> None:
        self._events.clear()

    def size(self) -> int:
        return len(self._events)

