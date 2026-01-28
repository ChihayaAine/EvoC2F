from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .skills import SkillLibrary, SkillStatus
from ..policies.gating import GatingPolicy


@dataclass
class SkillGateResult:
    allowed: bool
    reason: str


class SkillManager:
    def __init__(self, library: SkillLibrary, gating: Optional[GatingPolicy] = None) -> None:
        self.library = library
        self.gating = gating or GatingPolicy()

    def promote(self, name: str, metrics: Dict[str, float]) -> SkillGateResult:
        if not self.gating.allow(metrics):
            return SkillGateResult(False, "gating_rejected")
        self.library.update_status(name, SkillStatus.STABLE)
        return SkillGateResult(True, "promoted")

    def canary(self, name: str) -> None:
        self.library.update_status(name, SkillStatus.CANARY)

    def shadow(self, name: str) -> None:
        self.library.update_status(name, SkillStatus.SHADOW)

    def deprecate(self, name: str) -> None:
        self.library.update_status(name, SkillStatus.DEPRECATED)

    def refresh(self) -> None:
        self.library.refresh_deployments()

