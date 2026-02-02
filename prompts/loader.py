from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set


@dataclass
class PromptRenderError(Exception):
    message: str
    missing_keys: Set[str]

    def __str__(self) -> str:
        return f"{self.message}: {sorted(self.missing_keys)}"


class PromptLoader:
    def __init__(self, root: str, cache: bool = True) -> None:
        self.root = Path(root)
        self._cache: Dict[str, str] = {}
        self._cache_enabled = cache

    def load(self, name: str) -> str:
        path = self.root / "templates" / name
        if self._cache_enabled and name in self._cache:
            return self._cache[name]
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {name}")
        content = path.read_text(encoding="utf-8")
        if self._cache_enabled:
            self._cache[name] = content
        return content

    def render(self, name: str, variables: Dict[str, str]) -> str:
        template = self.load(name)
        missing = self.missing_variables(template, variables.keys())
        if missing:
            raise PromptRenderError("Missing variables", missing)
        return template.format(**variables)

    def load_optional(self, name: str, default: str = "") -> str:
        path = self.root / "templates" / name
        if not path.exists():
            return default
        return self.load(name)

    def list(self) -> Dict[str, str]:
        templates = {}
        for file in (self.root / "templates").glob("*.txt"):
            templates[file.name] = file.read_text(encoding="utf-8")
        return templates

    def list_names(self) -> List[str]:
        return sorted([file.name for file in (self.root / "templates").glob("*.txt")])

    def clear_cache(self) -> None:
        self._cache.clear()

    def refresh(self, names: Optional[Iterable[str]] = None) -> None:
        if not self._cache_enabled:
            return
        if names is None:
            self.clear_cache()
            return
        for name in names:
            self._cache.pop(name, None)

    def missing_variables(self, template: str, provided: Iterable[str]) -> Set[str]:
        required = set()
        for token in template.split("{"):
            if "}" not in token:
                continue
            key = token.split("}")[0].strip()
            if key and ":" not in key:
                required.add(key)
        return required - set(provided)

