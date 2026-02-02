from .executor import ExecutionConfig, ExecutionResult, Executor
from ..core.plan_ir import ToolRegistry


def build_executor(
    registry: ToolRegistry,
    config: ExecutionConfig,
    rate_limits=None,
    rate_bursts=None,
) -> Executor:
    return Executor(registry, rate_limits=rate_limits, rate_bursts=rate_bursts, config=config)

__all__ = ["ExecutionConfig", "ExecutionResult", "Executor", "build_executor"]

