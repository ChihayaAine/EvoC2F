from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any

from core.compiler import CompilerConfig
from planning.planner import PlannerConfig
from runtime.executor import ExecutionConfig
from verification.verification import VerificationConfig


@dataclass
class RuntimeLimits:
    max_cost: float = 10.0
    max_concurrency: int = 4
    deadline_ms: float = 30_000.0
    rate_limits: Dict[str, float] = field(default_factory=dict)
    rate_bursts: Dict[str, float] = field(default_factory=dict)

    def validate(self) -> None:
        if self.max_cost <= 0:
            raise ValueError("max_cost must be positive")
        if self.max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive")
        if self.deadline_ms <= 0:
            raise ValueError("deadline_ms must be positive")
        for resource, limit in self.rate_limits.items():
            if limit <= 0:
                raise ValueError(f"rate_limits[{resource}] must be positive")
        for resource, burst in self.rate_bursts.items():
            if burst <= 0:
                raise ValueError(f"rate_bursts[{resource}] must be positive")

    def normalize(self) -> "RuntimeLimits":
        bursts = dict(self.rate_bursts)
        for resource, limit in self.rate_limits.items():
            bursts.setdefault(resource, limit)
        return RuntimeLimits(
            max_cost=self.max_cost,
            max_concurrency=self.max_concurrency,
            deadline_ms=self.deadline_ms,
            rate_limits=self.rate_limits,
            rate_bursts=bursts,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_cost": self.max_cost,
            "max_concurrency": self.max_concurrency,
            "deadline_ms": self.deadline_ms,
            "rate_limits": dict(self.rate_limits),
            "rate_bursts": dict(self.rate_bursts),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RuntimeLimits":
        return cls(
            max_cost=float(payload.get("max_cost", 10.0)),
            max_concurrency=int(payload.get("max_concurrency", 4)),
            deadline_ms=float(payload.get("deadline_ms", 30_000.0)),
            rate_limits=dict(payload.get("rate_limits", {})),
            rate_bursts=dict(payload.get("rate_bursts", {})),
        )


@dataclass
class Defaults:
    planner_top_k: int = 5
    retry_max: int = 2
    retry_gamma: float = 2.0
    retry_jitter: float = 0.0

    def compiler(self, limits: RuntimeLimits) -> CompilerConfig:
        limits = limits.normalize()
        return CompilerConfig(
            concurrency_limit=limits.max_concurrency,
            deadline_ms=limits.deadline_ms,
            rate_limits=limits.rate_limits,
            rate_bursts=limits.rate_bursts,
        )

    def executor(self, limits: RuntimeLimits) -> ExecutionConfig:
        limits = limits.normalize()
        return ExecutionConfig(
            concurrency_limit=limits.max_concurrency,
            jitter=self.retry_jitter,
        )

    def verification(self) -> VerificationConfig:
        return VerificationConfig()

    def planner(self) -> PlannerConfig:
        return PlannerConfig(top_k_skills=self.planner_top_k)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "planner_top_k": self.planner_top_k,
            "retry_max": self.retry_max,
            "retry_gamma": self.retry_gamma,
            "retry_jitter": self.retry_jitter,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Defaults":
        return cls(
            planner_top_k=int(payload.get("planner_top_k", 5)),
            retry_max=int(payload.get("retry_max", 2)),
            retry_gamma=float(payload.get("retry_gamma", 2.0)),
            retry_jitter=float(payload.get("retry_jitter", 0.0)),
        )

