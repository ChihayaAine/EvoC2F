from __future__ import annotations

import random
from dataclasses import dataclass

from core.plan_ir import RetryPolicy


@dataclass
class RetryPolicyConfig:
    max_retries: int = 2
    backoff_gamma: float = 2.0
    jitter: float = 0.0

    def backoff(self, attempt: int, base: float = 0.1, max_backoff: float = 2.0) -> float:
        delay = min(max_backoff, base * (self.backoff_gamma ** (attempt - 1)))
        if self.jitter:
            delay *= 1.0 + random.uniform(-self.jitter, self.jitter)
        return max(0.0, delay)

    def as_retry_policy(self) -> RetryPolicy:
        return RetryPolicy(
            max_retries=self.max_retries,
            backoff_gamma=self.backoff_gamma,
            jitter=self.jitter,
        )

