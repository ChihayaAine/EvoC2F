"""Configuration defaults for EvoC2F components."""

from .defaults import Defaults, RuntimeLimits

def default_config() -> Defaults:
    return Defaults()


def default_limits() -> RuntimeLimits:
    return RuntimeLimits()


__all__ = ["Defaults", "RuntimeLimits", "default_config", "default_limits"]

