from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class ModelResponse:
    text: str
    metadata: Dict[str, Any]
    tokens_prompt: int = 0
    tokens_completion: int = 0
    finish_reason: str = "stop"

    @property
    def tokens_total(self) -> int:
        return self.tokens_prompt + self.tokens_completion


@dataclass
class ModelRequest:
    prompt: str
    temperature: float = 0.0
    max_tokens: int = 256
    stop: Optional[Sequence[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseModel:
    def generate(self, prompt: str, **kwargs: Any) -> ModelResponse:
        raise NotImplementedError

    def generate_request(self, request: ModelRequest) -> ModelResponse:
        return self.generate(
            request.prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stop=request.stop,
            metadata=request.metadata,
        )

    def generate_batch(self, prompts: Sequence[str], **kwargs: Any) -> List[ModelResponse]:
        return [self.generate(prompt, **kwargs) for prompt in prompts]

    def count_tokens(self, text: str) -> int:
        return len(text.split())

