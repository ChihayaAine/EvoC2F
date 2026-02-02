from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter
from typing import Dict, Iterable, List, Optional, Tuple


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

    def summary_with_percentiles(self, name: str, percentiles: Iterable[float]) -> Dict[str, float]:
        values = sorted(self.histograms.get(name, []))
        if not values:
            return {"count": 0.0, "min": 0.0, "max": 0.0, "avg": 0.0}
        summary = self.summary(name)
        for p in percentiles:
            summary[f"p{int(p * 100)}"] = _percentile(values, p)
        return summary

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

    def top_counters(self, k: int = 5) -> List[Tuple[str, int]]:
        return sorted(self.counters.items(), key=lambda kv: kv[1], reverse=True)[:k]

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {k: list(v) for k, v in self.histograms.items()},
        }

    def load(self, payload: Dict[str, Dict[str, float]]) -> None:
        self.counters.update({k: int(v) for k, v in payload.get("counters", {}).items()})
        self.gauges.update({k: float(v) for k, v in payload.get("gauges", {}).items()})
        for key, values in payload.get("histograms", {}).items():
            if isinstance(values, list):
                self.histograms[key] = [float(v) for v in values]


def _percentile(sorted_values: List[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if p <= 0:
        return float(sorted_values[0])
    if p >= 1:
        return float(sorted_values[-1])
    idx = int(round((len(sorted_values) - 1) * p))
    return float(sorted_values[idx])

