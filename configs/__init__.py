from .defaults import Defaults, RuntimeLimits

def default_config() -> Defaults:
    return Defaults()


__all__ = ["Defaults", "RuntimeLimits", "default_config"]

