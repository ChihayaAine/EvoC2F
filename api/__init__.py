"""API entrypoints for EvoC2F service orchestration."""

from typing import Optional

from .service import EvoC2FService, ServiceConfig
from configs.defaults import Defaults, RuntimeLimits


def build_service_config(limits: Optional[RuntimeLimits] = None) -> ServiceConfig:
    limits = limits or RuntimeLimits()
    defaults = Defaults()
    return ServiceConfig(
        compiler=defaults.compiler(limits),
        executor=defaults.executor(limits),
        planner=defaults.planner(),
    )


def build_service(registry, skills, limits: Optional[RuntimeLimits] = None) -> EvoC2FService:
    return EvoC2FService(registry=registry, skills=skills, config=build_service_config(limits))


__all__ = ["EvoC2FService", "ServiceConfig", "build_service_config", "build_service"]

