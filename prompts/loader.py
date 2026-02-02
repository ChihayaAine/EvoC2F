from __future__ import annotations

from pathlib import Path
from typing import Dict


class PromptLoader:
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self._cache: Dict[str, str] = {}

    def load(self, name: str) -> str:
        path = self.root / "templates" / name
        if name in self._cache:
            return self._cache[name]
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {name}")
        content = path.read_text(encoding="utf-8")
        self._cache[name] = content
        return content

    def list(self) -> Dict[str, str]:
        templates = {}
        for file in (self.root / "templates").glob("*.txt"):
            templates[file.name] = file.read_text(encoding="utf-8")
        return templates

    def clear_cache(self) -> None:
        self._cache.clear()

