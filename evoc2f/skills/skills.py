from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple

from ..core.plan_ir import Skill


class SkillStatus(str, Enum):
    SHADOW = "shadow"
    CANARY = "canary"
    STABLE = "stable"
    DEPRECATED = "deprecated"


@dataclass
class SkillMetrics:
    success_rate: float = 1.0
    avg_cost: float = 0.0
    last_used_ts: float = 0.0
    usage_count: int = 0


@dataclass
class SkillLibrary:
    skills: Dict[str, Skill] = field(default_factory=dict)
    metrics: Dict[str, SkillMetrics] = field(default_factory=dict)
    canary_fraction: float = 0.1
    min_success_rate: float = 0.95

    def add(self, skill: Skill) -> None:
        self.skills[skill.name] = skill
        self.metrics.setdefault(skill.name, SkillMetrics())

    def update_status(self, name: str, status: SkillStatus) -> None:
        if name in self.skills:
            self.skills[name].status = status.value

    def get(self, name: str) -> Skill:
        return self.skills[name]

    def active_skills(self) -> List[Skill]:
        active = []
        for skill in self.skills.values():
            if skill.status in {SkillStatus.STABLE.value, SkillStatus.CANARY.value}:
                active.append(skill)
            elif skill.status == SkillStatus.SHADOW.value:
                active.append(skill)
        return active

    def eligible_for_execution(self, skill: Skill) -> bool:
        if skill.status == SkillStatus.DEPRECATED.value:
            return False
        if skill.status == SkillStatus.SHADOW.value:
            return False
        if skill.status == SkillStatus.CANARY.value:
            return True
        return True

    def should_execute(self, skill: Skill, rng: Optional[float] = None) -> bool:
        if not self.eligible_for_execution(skill):
            return False
        if skill.status == SkillStatus.CANARY.value:
            if rng is None:
                return True
            return rng <= self.canary_fraction
        return True

    def record_usage(self, name: str, success: bool, cost: float, ts: float) -> None:
        metric = self.metrics.setdefault(name, SkillMetrics())
        metric.usage_count += 1
        metric.last_used_ts = ts
        if metric.usage_count == 1:
            metric.success_rate = 1.0 if success else 0.0
            metric.avg_cost = cost
        else:
            metric.success_rate = (
                metric.success_rate * (metric.usage_count - 1) + (1.0 if success else 0.0)
            ) / metric.usage_count
            metric.avg_cost = (
                metric.avg_cost * (metric.usage_count - 1) + cost
            ) / metric.usage_count

    def demote_if_needed(self, name: str, min_success: float) -> None:
        metric = self.metrics.get(name)
        if not metric:
            return
        if metric.success_rate < min_success and name in self.skills:
            self.skills[name].status = SkillStatus.DEPRECATED.value

    def refresh_deployments(self) -> None:
        for name, metric in self.metrics.items():
            if metric.success_rate < self.min_success_rate:
                self.demote_if_needed(name, self.min_success_rate)

