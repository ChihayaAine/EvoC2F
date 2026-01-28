from __future__ import annotations

import time
from typing import Any, Dict, Optional

from .base import BaseModel, ModelResponse


class LocalModelStub(BaseModel):
    def __init__(self, fixed_response: str = "", latency_ms: float = 0.0) -> None:
        self.fixed_response = fixed_response
        self.latency_ms = latency_ms

    def generate(self, prompt: str, **kwargs: Any) -> ModelResponse:
        if self.latency_ms:
            time.sleep(self.latency_ms / 1000.0)
        text = self.fixed_response if self.fixed_response else prompt
        max_tokens: Optional[int] = kwargs.get("max_tokens")
        if max_tokens is not None:
            tokens = text.split()
            text = " ".join(tokens[:max_tokens])
        metadata = {"prompt": prompt}
        metadata.update(kwargs.get("metadata") or {})
        tokens_prompt = len(prompt.split())
        tokens_completion = len(text.split())
        return ModelResponse(
            text=text,
            metadata=metadata,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
        )

