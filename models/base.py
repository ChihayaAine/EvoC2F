from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


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
    top_p: Optional[float] = None
    seed: Optional[int] = None


class BaseModel:
    def generate(self, prompt: str, **kwargs: Any) -> ModelResponse:
        text = prompt
        max_tokens: Optional[int] = kwargs.get("max_tokens")
        stop: Optional[Sequence[str]] = kwargs.get("stop")
        if stop:
            for token in stop:
                idx = text.find(token)
                if idx >= 0:
                    text = text[:idx]
                    break
        if max_tokens is not None:
            tokens = text.split()
            text = " ".join(tokens[:max_tokens])
        metadata = {"prompt": prompt}
        metadata.update(kwargs.get("metadata") or {})
        tokens_prompt = self.count_tokens(prompt)
        tokens_completion = self.count_tokens(text)
        return ModelResponse(
            text=text,
            metadata=metadata,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
        )

    def generate_request(self, request: ModelRequest) -> ModelResponse:
        return self.generate(
            request.prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stop=request.stop,
            metadata=request.metadata,
            top_p=request.top_p,
            seed=request.seed,
        )

    def generate_batch(self, prompts: Sequence[str], **kwargs: Any) -> List[ModelResponse]:
        return [self.generate(prompt, **kwargs) for prompt in prompts]

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def count_tokens_batch(self, texts: Iterable[str]) -> List[int]:
        return [self.count_tokens(text) for text in texts]

    def estimate_cost(self, tokens_prompt: int, tokens_completion: int, price_per_1k: float) -> float:
        total = tokens_prompt + tokens_completion
        return (total / 1000.0) * price_per_1k

    def validate_request(self, request: ModelRequest) -> Tuple[bool, Optional[str]]:
        if request.max_tokens < 0:
            return False, "max_tokens must be non-negative"
        if request.temperature < 0:
            return False, "temperature must be non-negative"
        if request.top_p is not None and not (0.0 < request.top_p <= 1.0):
            return False, "top_p must be in (0,1]"
        return True, None

