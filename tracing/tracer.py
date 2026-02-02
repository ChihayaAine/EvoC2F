from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional

from .events import TraceStore


@dataclass
class TraceSpan:
    name: str
    start_time: float
    payload: Dict[str, Any] = field(default_factory=dict)
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    parent_id: Optional[str] = None
    end_time: Optional[float] = None

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000.0


class Tracer:
    def __init__(self, store: Optional[TraceStore] = None) -> None:
        self.store = store or TraceStore()
        self.session_id = uuid.uuid4().hex
        self._tags: Dict[str, Any] = {}

    def event(self, name: str, payload: Optional[Dict[str, Any]] = None) -> None:
        enriched = dict(self._tags)
        if payload:
            enriched.update(payload)
        enriched.setdefault("session_id", self.session_id)
        self.store.emit(name, enriched)

    def add_tags(self, tags: Dict[str, Any]) -> None:
        self._tags.update(tags)

    @contextmanager
    def span(
        self, name: str, payload: Optional[Dict[str, Any]] = None, parent_id: Optional[str] = None
    ) -> Iterator[TraceSpan]:
        span = TraceSpan(name=name, start_time=time.time(), payload=payload or {}, parent_id=parent_id)
        self.event(f"{name}.start", {"span_id": span.span_id, "parent_id": parent_id, **span.payload})
        try:
            yield span
            span.end_time = time.time()
            self.event(
                f"{name}.end",
                {
                    "span_id": span.span_id,
                    "parent_id": parent_id,
                    "duration_ms": span.duration_ms,
                },
            )
        except Exception as exc:
            span.end_time = time.time()
            self.event(
                f"{name}.error",
                {
                    "span_id": span.span_id,
                    "parent_id": parent_id,
                    "duration_ms": span.duration_ms,
                    "error": str(exc),
                },
            )
            raise

    def record_exception(self, name: str, exc: Exception) -> None:
        self.event(name, {"error": str(exc)})

