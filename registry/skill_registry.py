from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core.plan_ir import Skill


@dataclass
class RegistryStats:
    total: int = 0
    active: int = 0
    deprecated: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {"total": self.total, "active": self.active, "deprecated": self.deprecated}


class InMemorySkillRegistry:
    def __init__(self) -> None:
        self._skills: Dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        return self._skills[name]

    def get_optional(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list(self) -> List[Skill]:
        return list(self._skills.values())

    def exists(self, name: str) -> bool:
        return name in self._skills

    def list_active(self) -> List[Skill]:
        return [skill for skill in self._skills.values() if skill.status != "deprecated"]

    def search(self, keyword: str) -> List[Skill]:
        keyword_lower = keyword.lower()
        return [
            skill
            for skill in self._skills.values()
            if keyword_lower in skill.name.lower() or keyword_lower in skill.description.lower()
        ]

    def search_tag(self, tag: str) -> List[Skill]:
        matched: List[Skill] = []
        for skill in self._skills.values():
            tags = skill.metadata.get("tags", [])
            if isinstance(tags, list) and tag in tags:
                matched.append(skill)
        return matched

    def filter(self, predicate: Callable[[Skill], bool]) -> List[Skill]:
        return [skill for skill in self._skills.values() if predicate(skill)]

    def remove(self, name: str) -> None:
        if name in self._skills:
            self._skills.pop(name)

    def register_many(self, skills: Iterable[Skill]) -> None:
        for skill in skills:
            self.register(skill)

    def update(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def count(self) -> int:
        return len(self._skills)

    def stats(self) -> RegistryStats:
        total = len(self._skills)
        active = len(self.list_active())
        deprecated = total - active
        return RegistryStats(total=total, active=active, deprecated=deprecated)

    def export(self) -> Dict[str, Any]:
        return {"skills": [self._serialize(skill) for skill in self._skills.values()]}

    def load(self, payload: Dict[str, Any]) -> None:
        for skill_data in payload.get("skills", []):
            skill = self._deserialize(skill_data)
            self.register(skill)

    def _serialize(self, skill: Skill) -> Dict[str, Any]:
        return {
            "name": skill.name,
            "description": skill.description,
            "status": skill.status,
            "metadata": dict(skill.metadata),
        }

    def _deserialize(self, payload: Dict[str, Any]) -> Skill:
        tool = Skill(
            name=payload["name"],
            signature=lambda **kwargs: kwargs,
            effect=payload.get("effect") or skill_effect_fallback(),
            resources=tuple(),
            expected_latency_ms=float(payload.get("expected_latency_ms", 0.0)),
            expected_cost=float(payload.get("expected_cost", 0.0)),
            description=payload.get("description", ""),
            status=payload.get("status", "shadow"),
            metadata=payload.get("metadata", {}),
        )
        return tool


def skill_effect_fallback() -> "EffectType":
    from core.plan_ir import EffectType, Environment, SideEffect

    return EffectType(side_effect=SideEffect.READ, environment=Environment.LOCAL)

