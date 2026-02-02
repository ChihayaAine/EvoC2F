from .skill_registry import InMemorySkillRegistry
from .tool_registry import InMemoryToolRegistry


def default_skill_registry() -> InMemorySkillRegistry:
    return InMemorySkillRegistry()


def default_tool_registry() -> InMemoryToolRegistry:
    return InMemoryToolRegistry()

__all__ = [
    "InMemorySkillRegistry",
    "InMemoryToolRegistry",
    "default_skill_registry",
    "default_tool_registry",
]

