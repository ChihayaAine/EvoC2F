"""Tracing primitives for EvoC2F execution."""

from .events import TraceEvent, TraceStore
from .exporter import TraceExporter
from .tracer import TraceSpan, Tracer


def new_tracer(capacity: int | None = None) -> Tracer:
    store = TraceStore(capacity=capacity) if capacity else TraceStore()
    return Tracer(store=store)


__all__ = ["TraceEvent", "TraceStore", "TraceExporter", "TraceSpan", "Tracer", "new_tracer"]

