from .base import TaskResult, TaskRunner, TaskSpec, TaskSuite
from .runner import FunctionTaskRunner


def build_function_task(
    name: str,
    description: str,
    handler,
    input_schema=None,
    output_schema=None,
) -> FunctionTaskRunner:
    return FunctionTaskRunner(
        TaskSpec(
            name=name,
            description=description,
            input_schema=input_schema or {},
            output_schema=output_schema or {},
        ),
        handler,
    )

__all__ = [
    "TaskResult",
    "TaskRunner",
    "TaskSpec",
    "TaskSuite",
    "FunctionTaskRunner",
    "build_function_task",
]

