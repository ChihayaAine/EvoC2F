from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Iterator, List, Optional


class DatasetSplit(str, Enum):
    TRAIN = "train"
    DEV = "dev"
    TEST = "test"


@dataclass
class Example:
    task: str
    input: Dict[str, str]
    output: Dict[str, str]
    metadata: Dict[str, str]


class JsonlDataset:
    def __init__(self, path: str) -> None:
        self.path = path

    def __iter__(self) -> Iterator[Example]:
        with open(self.path, "r", encoding="utf-8") as handle:
            for line in handle:
                payload = json.loads(line)
                yield Example(
                    task=payload.get("task", ""),
                    input=payload.get("input", {}),
                    output=payload.get("output", {}),
                    metadata=payload.get("metadata", {}),
                )

    def take(self, limit: int) -> List[Example]:
        items: List[Example] = []
        for idx, item in enumerate(self):
            if idx >= limit:
                break
            items.append(item)
        return items

    def filter(self, task: Optional[str] = None) -> Iterator[Example]:
        for item in self:
            if task and item.task != task:
                continue
            yield item

