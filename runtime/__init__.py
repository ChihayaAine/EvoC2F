"""Runtime execution helpers."""

from typing import Dict, Optional

from .executor import ExecutionConfig, ExecutionResult, Executor
from core.plan_ir import ToolRegistry


def build_executor(
    registry: ToolRegistry,
    config: ExecutionConfig,
    rate_limits: Optional[Dict[str, float]] = None,
    rate_bursts: Optional[Dict[str, float]] = None,
) -> Executor:
    return Executor(registry, rate_limits=rate_limits, rate_bursts=rate_bursts, config=config)

__all__ = ["ExecutionConfig", "ExecutionResult", "Executor", "build_executor"]

