from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core.plan_ir import Skill


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
    regression_rate: float = 0.0
    failure_count: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "success_rate": self.success_rate,
            "avg_cost": self.avg_cost,
            "last_used_ts": self.last_used_ts,
            "usage_count": self.usage_count,
            "regression_rate": self.regression_rate,
            "failure_count": self.failure_count,
        }

    def update_from(self, payload: Dict[str, Any]) -> None:
        self.success_rate = float(payload.get("success_rate", self.success_rate))
        self.avg_cost = float(payload.get("avg_cost", self.avg_cost))
        self.last_used_ts = float(payload.get("last_used_ts", self.last_used_ts))
        self.usage_count = int(payload.get("usage_count", self.usage_count))
        self.regression_rate = float(payload.get("regression_rate", self.regression_rate))
        self.failure_count = int(payload.get("failure_count", self.failure_count))


@dataclass
class SkillLibrary:
    skills: Dict[str, Skill] = field(default_factory=dict)
    metrics: Dict[str, SkillMetrics] = field(default_factory=dict)
    canary_fraction: float = 0.1
    min_success_rate: float = 0.95
    min_canary_samples: int = 30

    def add(self, skill: Skill) -> None:
        self.skills[skill.name] = skill
        self.metrics.setdefault(skill.name, SkillMetrics())

    def add_many(self, skills: Iterable[Skill]) -> None:
        for skill in skills:
            self.add(skill)

    def update_status(self, name: str, status: SkillStatus) -> None:
        if name in self.skills:
            self.skills[name].status = status.value

    def get(self, name: str) -> Skill:
        return self.skills[name]

    def remove(self, name: str) -> None:
        if name in self.skills:
            self.skills.pop(name)
        if name in self.metrics:
            self.metrics.pop(name)

    def active_skills(self) -> List[Skill]:
        active = []
        for skill in self.skills.values():
            if skill.status in {SkillStatus.STABLE.value, SkillStatus.CANARY.value}:
                active.append(skill)
            elif skill.status == SkillStatus.SHADOW.value:
                active.append(skill)
        return active

    def list_by_status(self, status: SkillStatus) -> List[Skill]:
        return [skill for skill in self.skills.values() if skill.status == status.value]

    def list_by_tag(self, tag: str) -> List[Skill]:
        matched = []
        for skill in self.skills.values():
            tags = skill.metadata.get("tags", [])
            if isinstance(tags, list) and tag in tags:
                matched.append(skill)
        return matched

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
                import random

                rng = random.random()
            return rng <= self.canary_fraction
        return True

    def health_score(self, name: str) -> float:
        metric = self.metrics.get(name)
        if not metric:
            return 0.0
        score = metric.success_rate - metric.regression_rate
        if metric.usage_count:
            penalty = min(0.2, metric.failure_count / max(metric.usage_count, 1) * 0.2)
            score -= penalty
        return max(0.0, min(1.0, score))

    def record_usage(self, name: str, success: bool, cost: float, ts: float) -> None:
        metric = self.metrics.setdefault(name, SkillMetrics())
        metric.usage_count += 1
        metric.last_used_ts = ts
        if not success:
            metric.failure_count += 1
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

    def record_regression(self, name: str, regression: bool) -> None:
        metric = self.metrics.setdefault(name, SkillMetrics())
        if metric.usage_count == 0:
            metric.regression_rate = 1.0 if regression else 0.0
            return
        metric.regression_rate = (
            metric.regression_rate * (metric.usage_count - 1) + (1.0 if regression else 0.0)
        ) / metric.usage_count

    def get_metrics(self, name: str) -> Optional[SkillMetrics]:
        return self.metrics.get(name)

    def snapshot_metrics(self) -> Dict[str, Dict[str, Any]]:
        return {name: metric.as_dict() for name, metric in self.metrics.items()}

    def merge_metrics(self, payload: Dict[str, Dict[str, Any]]) -> None:
        for name, data in payload.items():
            metric = self.metrics.setdefault(name, SkillMetrics())
            metric.update_from(data)

    def most_used(self, k: int = 5) -> List[Skill]:
        ranked = sorted(
            self.skills.values(),
            key=lambda s: self.metrics.get(s.name, SkillMetrics()).usage_count,
            reverse=True,
        )
        return ranked[:k]

    def prune_by_cost(self, max_cost: float) -> List[str]:
        removed: List[str] = []
        for name, metric in list(self.metrics.items()):
            if metric.avg_cost > max_cost:
                self.skills[name].status = SkillStatus.DEPRECATED.value
                removed.append(name)
        return removed

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
                continue
            skill = self.skills.get(name)
            if not skill:
                continue
            if skill.status == SkillStatus.CANARY.value and metric.usage_count >= self.min_canary_samples:
                self.skills[name].status = SkillStatus.STABLE.value

    def export(
        self, serializer: Optional[Callable[[Skill], Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        if serializer is None:
            serializer = _default_skill_serializer
        return {
            "skills": {name: serializer(skill) for name, skill in self.skills.items()},
            "metrics": self.snapshot_metrics(),
        }

    def import_metrics_only(self, payload: Dict[str, Any]) -> None:
        metrics = payload.get("metrics", {})
        if isinstance(metrics, dict):
            self.merge_metrics(metrics)


def _default_skill_serializer(skill: Skill) -> Dict[str, Any]:
    return {
        "name": skill.name,
        "description": skill.description,
        "status": skill.status,
        "metadata": dict(skill.metadata),
    }

