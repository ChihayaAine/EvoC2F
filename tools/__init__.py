from .base import ToolAdapter, ToolCatalog, ToolSpec, ToolWrapper, ToolResult


def build_core_tool(spec: ToolSpec, handler, latency_ms: float, cost: float):
    return ToolAdapter(spec, handler).as_core_tool(latency_ms=latency_ms, cost=cost)


__all__ = [
    "ToolAdapter",
    "ToolCatalog",
    "ToolSpec",
    "ToolWrapper",
    "ToolResult",
    "build_core_tool",
]

