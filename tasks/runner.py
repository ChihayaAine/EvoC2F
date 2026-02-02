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
        try:
            output = self.handler(payload)
            success = output.get("success", True)
            error = None
        except Exception as exc:
            output = {"success": False, "error": str(exc)}
            success = False
            error = str(exc)
        elapsed = (perf_counter() - start) * 1000
        metrics = {"latency_ms": elapsed}
        if error:
            metrics["error"] = error
        return TaskResult(output=output, success=bool(success), metrics=metrics)

