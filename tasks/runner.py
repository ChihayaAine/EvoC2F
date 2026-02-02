from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from time import perf_counter, sleep
from typing import Any, Callable, Dict, Iterable, List, Optional

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


class RetryTaskRunner(TaskRunner):
    def __init__(self, runner: TaskRunner, max_retries: int = 2, backoff_s: float = 0.1) -> None:
        super().__init__(runner.task, handler=runner.handler)
        self._runner = runner
        self.max_retries = max_retries
        self.backoff_s = backoff_s

    def run(self, payload: Dict[str, Any]) -> TaskResult:
        attempt = 0
        last_result: Optional[TaskResult] = None
        while attempt <= self.max_retries:
            result = self._runner.run(payload)
            last_result = result
            if result.success:
                return result
            attempt += 1
            if attempt <= self.max_retries:
                sleep(self.backoff_s * attempt)
        return last_result or TaskResult(output={"success": False}, success=False)


class TimeoutTaskRunner(TaskRunner):
    def __init__(self, runner: TaskRunner, timeout_ms: float) -> None:
        super().__init__(runner.task, handler=runner.handler)
        self._runner = runner
        self.timeout_ms = timeout_ms

    def run(self, payload: Dict[str, Any]) -> TaskResult:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._runner.run, payload)
            try:
                return future.result(timeout=self.timeout_ms / 1000.0)
            except FutureTimeout:
                return TaskResult(
                    output={"success": False, "error": "task timeout"},
                    success=False,
                    metrics={"timeout_ms": self.timeout_ms},
                )


class BatchTaskRunner(TaskRunner):
    def __init__(self, runner: TaskRunner, max_concurrency: int = 4) -> None:
        super().__init__(runner.task, handler=runner.handler)
        self._runner = runner
        self.max_concurrency = max_concurrency

    def run_many(self, payloads: Iterable[Dict[str, Any]]) -> List[TaskResult]:
        results: List[TaskResult] = []
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            futures = [executor.submit(self._runner.run, payload) for payload in payloads]
            for future in futures:
                results.append(future.result())
        return results

