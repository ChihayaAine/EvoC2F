from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import random
import threading
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple


@dataclass
class Experience:
    task: str
    plan: Dict[str, Any]
    success: bool
    metadata: Dict[str, Any]
    timestamp: float = 0.0


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

    def add_many(self, experiences: Iterable[Experience]) -> None:
        self.extend(experiences)

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

    def filter_recent(self, limit: int = 100) -> List[Experience]:
        with self._lock:
            items = list(self._buffer)
        return items[-limit:]

    def success_rate(self, task: Optional[str] = None) -> float:
        items = self.filter(task=task)
        if not items:
            return 0.0
        return sum(1 for exp in items if exp.success) / len(items)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._buffer)
            successes = sum(1 for exp in self._buffer if exp.success)
            by_task: Dict[str, int] = {}
            for exp in self._buffer:
                by_task[exp.task] = by_task.get(exp.task, 0) + 1
        return {
            "total": total,
            "successes": successes,
            "success_rate": successes / total if total else 0.0,
            "tasks": by_task,
        }

    def deduplicate(self) -> int:
        with self._lock:
            seen: set[Tuple[str, str]] = set()
            unique: Deque[Experience] = deque(maxlen=self.capacity)
            removed = 0
            for exp in self._buffer:
                key = (exp.task, str(exp.plan))
                if key in seen:
                    removed += 1
                    continue
                seen.add(key)
                unique.append(exp)
            self._buffer = unique
        return removed

    def export(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "task": exp.task,
                    "plan": exp.plan,
                    "success": exp.success,
                    "metadata": exp.metadata,
                    "timestamp": exp.timestamp,
                }
                for exp in self._buffer
            ]

    def load(self, payload: List[Dict[str, Any]]) -> None:
        with self._lock:
            for item in payload:
                self._buffer.append(
                    Experience(
                        task=item.get("task", ""),
                        plan=item.get("plan", {}),
                        success=bool(item.get("success", False)),
                        metadata=item.get("metadata", {}),
                        timestamp=float(item.get("timestamp", 0.0)),
                    )
                )

