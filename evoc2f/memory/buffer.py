from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import random
import threading
from typing import Any, Deque, Dict, Iterable, List, Optional


@dataclass
class Experience:
    task: str
    plan: Dict[str, Any]
    success: bool
    metadata: Dict[str, Any]


class ExperienceBuffer:
    def __init__(self, capacity: int = 1000) -> None:
        self.capacity = capacity
        self._buffer: Deque[Experience] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def add(self, experience: Experience) -> None:
        with self._lock:
            self._buffer.append(experience)

    def extend(self, experiences: Iterable[Experience]) -> None:
        with self._lock:
            for exp in experiences:
                self._buffer.append(exp)

    def sample(self, k: int, randomize: bool = True) -> List[Experience]:
        with self._lock:
            items = list(self._buffer)
        if not items:
            return []
        if randomize:
            return random.sample(items, min(k, len(items)))
        return items[:k]

    def list(self) -> List[Experience]:
        with self._lock:
            return list(self._buffer)

    def filter(self, task: Optional[str] = None, success: Optional[bool] = None) -> List[Experience]:
        with self._lock:
            items = list(self._buffer)
        if task is not None:
            items = [exp for exp in items if exp.task == task]
        if success is not None:
            items = [exp for exp in items if exp.success == success]
        return items

    def success_rate(self, task: Optional[str] = None) -> float:
        items = self.filter(task=task)
        if not items:
            return 0.0
        return sum(1 for exp in items if exp.success) / len(items)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._buffer)
            successes = sum(1 for exp in self._buffer if exp.success)
        return {"total": total, "successes": successes, "success_rate": successes / total if total else 0.0}

