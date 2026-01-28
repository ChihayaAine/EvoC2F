from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import Dict, List


@dataclass
class MetricTracker:
    counters: Dict[str, int] = field(default_factory=dict)
    gauges: Dict[str, float] = field(default_factory=dict)
    histograms: Dict[str, List[float]] = field(default_factory=dict)

    def inc(self, name: str, value: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + value

    def set(self, name: str, value: float) -> None:
        self.gauges[name] = value

    def observe(self, name: str, value: float) -> None:
        self.histograms.setdefault(name, []).append(value)

    @contextmanager
    def timer(self, name: str) -> None:
        start = perf_counter()
        try:
            yield
        finally:
            elapsed = perf_counter() - start
            self.observe(name, elapsed)

    def summary(self, name: str) -> Dict[str, float]:
        values = self.histograms.get(name, [])
        if not values:
            return {"count": 0.0, "min": 0.0, "max": 0.0, "avg": 0.0}
        return {
            "count": float(len(values)),
            "min": float(min(values)),
            "max": float(max(values)),
            "avg": float(sum(values) / len(values)),
        }

    def merge(self, other: "MetricTracker") -> None:
        for key, value in other.counters.items():
            self.counters[key] = self.counters.get(key, 0) + value
        for key, value in other.gauges.items():
            self.gauges[key] = value
        for key, values in other.histograms.items():
            self.histograms.setdefault(key, []).extend(values)

    def reset(self) -> None:
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()

