"""Model adapters and utilities."""

from .base import BaseModel, ModelRequest, ModelResponse
from .stub import LocalModelStub


def build_stub(response: str = "", latency_ms: float = 0.0) -> LocalModelStub:
    return LocalModelStub(fixed_response=response, latency_ms=latency_ms)


__all__ = ["BaseModel", "ModelRequest", "ModelResponse", "LocalModelStub", "build_stub"]

