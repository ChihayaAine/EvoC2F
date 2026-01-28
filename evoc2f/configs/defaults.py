from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from ..core.compiler import CompilerConfig
from ..planning.planner import PlannerConfig
from ..runtime.executor import ExecutionConfig
from ..verification.verification import VerificationConfig


@dataclass
class RuntimeLimits:
    max_cost: float = 10.0
    max_concurrency: int = 4
    deadline_ms: float = 30_000.0
    rate_limits: Dict[str, float] = field(default_factory=dict)
    rate_bursts: Dict[str, float] = field(default_factory=dict)


@dataclass
class Defaults:
    planner_top_k: int = 5
    retry_max: int = 2
    retry_gamma: float = 2.0
    retry_jitter: float = 0.0

    def compiler(self, limits: RuntimeLimits) -> CompilerConfig:
        return CompilerConfig(
            concurrency_limit=limits.max_concurrency,
            deadline_ms=limits.deadline_ms,
            rate_limits=limits.rate_limits,
            rate_bursts=limits.rate_bursts,
        )

    def executor(self, limits: RuntimeLimits) -> ExecutionConfig:
        return ExecutionConfig(
            concurrency_limit=limits.max_concurrency,
            jitter=self.retry_jitter,
        )

    def verification(self) -> VerificationConfig:
        return VerificationConfig()

    def planner(self) -> PlannerConfig:
        return PlannerConfig(top_k_skills=self.planner_top_k)

