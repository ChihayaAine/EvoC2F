from __future__ import annotations

from typing import Dict


class GatingPolicy:
    def __init__(self, max_regression: float = 0.0, min_success_rate: float = 0.95) -> None:
        self.max_regression = max_regression
        self.min_success_rate = min_success_rate

    def allow(self, metrics: Dict[str, float]) -> bool:
        allowed, _ = self.evaluate(metrics)
        return allowed

    def evaluate(self, metrics: Dict[str, float]) -> tuple[bool, str]:
        regression = metrics.get("regression", 0.0)
        success_rate = metrics.get("success_rate", 1.0)
        if regression > self.max_regression:
            return False, "regression_exceeded"
        if success_rate < self.min_success_rate:
            return False, "success_rate_too_low"
        return True, "ok"

