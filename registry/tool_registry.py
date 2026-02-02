from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

from tools.base import ToolSpec


@dataclass
class ToolRegistryStats:
    total: int = 0
    active: int = 0
    deprecated: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {"total": self.total, "active": self.active, "deprecated": self.deprecated}


class InMemoryToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        spec.validate()
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        return self._tools[name]

    def get_optional(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def list(self) -> List[ToolSpec]:
        return list(self._tools.values())

    def list_active(self) -> List[ToolSpec]:
        return [spec for spec in self._tools.values() if not spec.deprecated]

    def search(self, tag: str) -> List[ToolSpec]:
        return [spec for spec in self._tools.values() if tag in spec.tags]

    def search_name(self, keyword: str) -> List[ToolSpec]:
        needle = keyword.lower()
        return [spec for spec in self._tools.values() if needle in spec.name.lower()]

    def search_owner(self, owner: str) -> List[ToolSpec]:
        return [spec for spec in self._tools.values() if spec.owner == owner]

    def filter(self, predicate: Callable[[ToolSpec], bool]) -> List[ToolSpec]:
        return [spec for spec in self._tools.values() if predicate(spec)]

    def exists(self, name: str) -> bool:
        return name in self._tools

    def remove(self, name: str) -> None:
        if name in self._tools:
            self._tools.pop(name)

    def register_many(self, specs: Iterable[ToolSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def update(self, spec: ToolSpec) -> None:
        spec.validate()
        self._tools[spec.name] = spec

    def count(self) -> int:
        return len(self._tools)

    def stats(self) -> ToolRegistryStats:
        total = len(self._tools)
        active = len(self.list_active())
        deprecated = total - active
        return ToolRegistryStats(total=total, active=active, deprecated=deprecated)

    def export(self) -> Dict[str, Any]:
        return {"tools": [spec.to_dict() for spec in self._tools.values()]}

    def load(self, payload: Dict[str, Any]) -> None:
        for spec_data in payload.get("tools", []):
            self.register(ToolSpec.from_dict(spec_data))

