from .gating import GatingPolicy
from .rate_limit import RateLimitPolicy
from .retry import RetryPolicyConfig

def default_gating() -> GatingPolicy:
    return GatingPolicy()


def default_retry() -> RetryPolicyConfig:
    return RetryPolicyConfig()


__all__ = [
    "GatingPolicy",
    "RateLimitPolicy",
    "RetryPolicyConfig",
    "default_gating",
    "default_retry",
]

