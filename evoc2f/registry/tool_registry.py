from __future__ import annotations

from typing import Dict, Iterable, List

from ..tools.base import ToolSpec


class InMemoryToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        return self._tools[name]

    def list(self) -> List[ToolSpec]:
        return list(self._tools.values())

    def list_active(self) -> List[ToolSpec]:
        return [spec for spec in self._tools.values() if not spec.deprecated]

    def search(self, tag: str) -> List[ToolSpec]:
        return [spec for spec in self._tools.values() if tag in spec.tags]

    def exists(self, name: str) -> bool:
        return name in self._tools

