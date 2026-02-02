from __future__ import annotations

from typing import Dict, List

from ..core.plan_ir import Skill


class InMemorySkillRegistry:
    def __init__(self) -> None:
        self._skills: Dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        return self._skills[name]

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

