from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class TaskSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    max_cost: float = 0.0
    max_latency_ms: float = 0.0

    def validate_input(self, payload: Dict[str, Any]) -> bool:
        return isinstance(payload, dict)

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return isinstance(payload, dict)


@dataclass
class TaskResult:
    output: Dict[str, Any]
    success: bool
    metrics: Dict[str, Any] = field(default_factory=dict)


class TaskRunner:
    def __init__(self, task: TaskSpec) -> None:
        self.task = task

    def run(self, payload: Dict[str, Any]) -> TaskResult:
        raise NotImplementedError

    def evaluate(self, result: TaskResult) -> float:
        return 1.0 if result.success else 0.0

    def validate(self, payload: Dict[str, Any]) -> None:
        if not self.task.validate_input(payload):
            raise ValueError("Invalid task input")


class TaskSuite:
    def __init__(self, tasks: Iterable[TaskSpec]) -> None:
        self.tasks = list(tasks)

    def list(self) -> List[TaskSpec]:
        return self.tasks

