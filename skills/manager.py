from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import Dict, Optional

from .skills import SkillLibrary, SkillStatus
from policies.gating import GatingPolicy


@dataclass
class SkillGateResult:
    allowed: bool
    reason: str


class SkillManager:
    def __init__(self, library: SkillLibrary, gating: Optional[GatingPolicy] = None) -> None:
        self.library = library
        self.gating = gating or GatingPolicy()

    def promote(self, name: str, metrics: Dict[str, float]) -> SkillGateResult:
        allowed, reason = self.gating.evaluate(metrics)
        if not allowed:
            return SkillGateResult(False, reason)
        self.library.update_status(name, SkillStatus.STABLE)
        return SkillGateResult(True, "promoted")

    def promote_from_library(self, name: str) -> SkillGateResult:
        metrics = self.library.get_metrics(name)
        if not metrics:
            return SkillGateResult(False, "missing_metrics")
        payload = {
            "regression": metrics.regression_rate,
            "success_rate": metrics.success_rate,
            "support": float(metrics.usage_count),
        }
        return self.promote(name, payload)

    def admit_shadow(self, name: str) -> None:
        self.library.update_status(name, SkillStatus.SHADOW)

    def canary(self, name: str) -> None:
        self.library.update_status(name, SkillStatus.CANARY)

    def shadow(self, name: str) -> None:
        self.library.update_status(name, SkillStatus.SHADOW)

    def deprecate(self, name: str) -> None:
        self.library.update_status(name, SkillStatus.DEPRECATED)

    def refresh(self) -> None:
        self.library.refresh_deployments()

    def evaluate_canary(self, name: str) -> SkillGateResult:
        metrics = self.library.get_metrics(name)
        if not metrics:
            return SkillGateResult(False, "missing_metrics")
        payload = {
            "regression": metrics.regression_rate,
            "success_rate": metrics.success_rate,
            "support": float(metrics.usage_count),
        }
        allowed, reason = self.gating.evaluate(payload)
        if not allowed:
            self.deprecate(name)
            return SkillGateResult(False, reason)
        self.library.update_status(name, SkillStatus.STABLE)
        return SkillGateResult(True, "canary_promoted")

    def record_outcome(self, name: str, success: bool, cost: float = 0.0) -> None:
        self.library.record_usage(name, success=success, cost=cost, ts=time())

    def record_regression(self, name: str, regression: bool) -> None:
        self.library.record_regression(name, regression)

    def canary_rollout(self, name: str, fraction: Optional[float] = None) -> None:
        if fraction is not None:
            self.library.canary_fraction = fraction
        self.library.update_status(name, SkillStatus.CANARY)

    def guardrail_demote(self, name: str, min_success: Optional[float] = None) -> SkillGateResult:
        metric = self.library.get_metrics(name)
        if not metric:
            return SkillGateResult(False, "missing_metrics")
        threshold = min_success if min_success is not None else self.library.min_success_rate
        if metric.success_rate < threshold:
            self.deprecate(name)
            return SkillGateResult(False, "success_rate_too_low")
        return SkillGateResult(True, "ok")

