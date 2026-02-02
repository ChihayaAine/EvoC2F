from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class RateLimitPolicy:
    limits_per_sec: Dict[str, float]
    bursts: Dict[str, float] = field(default_factory=dict)

    def validate(self) -> None:
        for resource, limit in self.limits_per_sec.items():
            if limit <= 0:
                raise ValueError(f"Rate limit must be positive for {resource}")
        for resource, burst in self.bursts.items():
            if burst <= 0:
                raise ValueError(f"Burst must be positive for {resource}")

    def normalize(self) -> "RateLimitPolicy":
        bursts = dict(self.bursts)
        for resource, limit in self.limits_per_sec.items():
            bursts.setdefault(resource, limit)
        return RateLimitPolicy(limits_per_sec=self.limits_per_sec, bursts=bursts)

