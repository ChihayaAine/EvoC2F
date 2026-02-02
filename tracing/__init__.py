"""Tracing primitives for EvoC2F execution."""

from .events import TraceEvent, TraceStore
from .exporter import TraceExporter
from .tracer import TraceSpan, Tracer


def new_tracer() -> Tracer:
    return Tracer()

__all__ = ["TraceEvent", "TraceStore", "TraceExporter", "TraceSpan", "Tracer", "new_tracer"]

