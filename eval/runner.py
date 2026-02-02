from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Dict, Iterable, List

from ..tasks.base import TaskResult, TaskRunner, TaskSpec


@dataclass
class EvalResult:
    total: int
    success: int
    scores: List[float] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)


class Evaluator:
    def __init__(self, runner: TaskRunner) -> None:
        self.runner = runner

    def run(self, inputs: Iterable[Dict[str, str]]) -> EvalResult:
        start = perf_counter()
        total = 0
        success = 0
        scores: List[float] = []
        for payload in inputs:
            total += 1
            result = self.runner.run(payload)
            success += 1 if result.success else 0
            scores.append(self.runner.evaluate(result))
        duration_ms = (perf_counter() - start) * 1000
        avg_score = sum(scores) / len(scores) if scores else 0.0
        return EvalResult(
            total=total,
            success=success,
            scores=scores,
            metrics={
                "success_rate": (success / total) if total else 0.0,
                "avg_score": avg_score,
                "duration_ms": duration_ms,
            },
        )

