from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable, Dict, Iterable, List, Optional

from schemas.json_schema import SchemaValidator


@dataclass
class TaskSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    max_cost: float = 0.0
    max_latency_ms: float = 0.0

    def validate_input(self, payload: Dict[str, Any]) -> bool:
        return not self.validate_input_errors(payload)

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return not self.validate_output_errors(payload)

    def validate_input_errors(self, payload: Dict[str, Any]) -> List[str]:
        if not isinstance(payload, dict):
            return ["Input must be object"]
        return SchemaValidator().validate(self.input_schema, payload)

    def validate_output_errors(self, payload: Dict[str, Any]) -> List[str]:
        if not isinstance(payload, dict):
            return ["Output must be object"]
        return SchemaValidator().validate(self.output_schema, payload)


@dataclass
class TaskResult:
    output: Dict[str, Any]
    success: bool
    metrics: Dict[str, Any] = field(default_factory=dict)


class TaskRunner:
    def __init__(self, task: TaskSpec, handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None) -> None:
        self.task = task
        self.handler = handler

    def run(self, payload: Dict[str, Any]) -> TaskResult:
        self.validate(payload)
        start = perf_counter()
        if not self.handler:
            return TaskResult(
                output={"success": False, "error": "handler not configured"},
                success=False,
                metrics={"latency_ms": (perf_counter() - start) * 1000},
            )
        try:
            output = self.handler(payload)
            if not isinstance(output, dict):
                output = {"success": False, "error": "handler output must be dict"}
            output_errors = self.task.validate_output_errors(output)
            success = output.get("success", True) and not output_errors
            metrics = {"latency_ms": (perf_counter() - start) * 1000}
            if output_errors:
                metrics["output_errors"] = output_errors
            return TaskResult(output=output, success=bool(success), metrics=metrics)
        except Exception as exc:
            return TaskResult(
                output={"success": False, "error": str(exc)},
                success=False,
                metrics={"latency_ms": (perf_counter() - start) * 1000, "error": str(exc)},
            )

    def evaluate(self, result: TaskResult) -> float:
        return 1.0 if result.success else 0.0

    def validate(self, payload: Dict[str, Any]) -> None:
        errors = self.task.validate_input_errors(payload)
        if errors:
            raise ValueError("; ".join(errors))


class TaskSuite:
    def __init__(self, tasks: Iterable[TaskSpec]) -> None:
        self.tasks = list(tasks)

    def list(self) -> List[TaskSpec]:
        return self.tasks

    def get(self, name: str) -> Optional[TaskSpec]:
        for task in self.tasks:
            if task.name == name:
                return task
        return None

    def summary(self) -> Dict[str, Any]:
        return {"total": len(self.tasks), "names": [task.name for task in self.tasks]}

