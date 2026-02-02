from __future__ import annotations

from time import perf_counter
from typing import Any, Callable, Dict

from .base import TaskResult, TaskRunner, TaskSpec


class FunctionTaskRunner(TaskRunner):
    def __init__(self, task: TaskSpec, handler: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        super().__init__(task)
        self.handler = handler

    def run(self, payload: Dict[str, Any]) -> TaskResult:
        self.validate(payload)
        start = perf_counter()
        output = self.handler(payload)
        elapsed = (perf_counter() - start) * 1000
        success = output.get("success", True)
        metrics = {"latency_ms": elapsed}
        return TaskResult(output=output, success=bool(success), metrics=metrics)

