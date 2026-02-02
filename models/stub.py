from __future__ import annotations

import random
import time
from typing import Any, Dict, Optional

from .base import BaseModel, ModelResponse


class LocalModelStub(BaseModel):
    def __init__(self, fixed_response: str = "", latency_ms: float = 0.0, echo_prompt: bool = False) -> None:
        self.fixed_response = fixed_response
        self.latency_ms = latency_ms
        self.echo_prompt = echo_prompt

    def generate(self, prompt: str, **kwargs: Any) -> ModelResponse:
        if self.latency_ms:
            time.sleep(self.latency_ms / 1000.0)
        if self.echo_prompt:
            text = prompt
        else:
            text = self.fixed_response if self.fixed_response else prompt
        max_tokens: Optional[int] = kwargs.get("max_tokens")
        if max_tokens is not None:
            tokens = text.split()
            text = " ".join(tokens[:max_tokens])
        metadata = {"prompt": prompt}
        metadata.update(kwargs.get("metadata") or {})
        tokens_prompt = len(prompt.split())
        tokens_completion = len(text.split())
        if "seed" in kwargs and kwargs["seed"] is not None:
            random.seed(kwargs["seed"])
        return ModelResponse(
            text=text,
            metadata=metadata,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
        )

