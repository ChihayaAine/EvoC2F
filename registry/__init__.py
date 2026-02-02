from .skill_registry import InMemorySkillRegistry, RegistryStats
from .tool_registry import InMemoryToolRegistry, ToolRegistryStats


def default_skill_registry() -> InMemorySkillRegistry:
    return InMemorySkillRegistry()


def default_tool_registry() -> InMemoryToolRegistry:
    return InMemoryToolRegistry()

__all__ = [
    "InMemorySkillRegistry",
    "InMemoryToolRegistry",
    "RegistryStats",
    "ToolRegistryStats",
    "default_skill_registry",
    "default_tool_registry",
]

