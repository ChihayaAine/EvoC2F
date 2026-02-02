from __future__ import annotations

import math
from typing import Iterable, List, Sequence


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def cosine_distance(a: List[float], b: List[float]) -> float:
    return 1.0 - cosine_similarity(a, b)


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def l2_norm(a: Sequence[float]) -> float:
    return math.sqrt(sum(x * x for x in a))


def normalize(a: Sequence[float]) -> List[float]:
    norm = l2_norm(a)
    if norm == 0:
        return [0.0 for _ in a]
    return [x / norm for x in a]


def softmax(values: Sequence[float]) -> List[float]:
    if not values:
        return []
    max_v = max(values)
    exps = [math.exp(v - max_v) for v in values]
    total = sum(exps)
    if total == 0:
        return [0.0 for _ in values]
    return [v / total for v in exps]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


def variance(values: Iterable[float]) -> float:
    values = list(values)
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return sum((x - m) ** 2 for x in values) / (len(values) - 1)


class MLP:
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int) -> None:
        self.w1 = [[0.01 for _ in range(input_dim)] for _ in range(hidden_dim)]
        self.b1 = [0.0 for _ in range(hidden_dim)]
        self.w2 = [[0.01 for _ in range(hidden_dim)] for _ in range(output_dim)]
        self.b2 = [0.0 for _ in range(output_dim)]

    def forward(self, x: List[float]) -> List[float]:
        h = []
        for i, weights in enumerate(self.w1):
            z = sum(w * xi for w, xi in zip(weights, x)) + self.b1[i]
            h.append(max(0.0, z))
        out = []
        for i, weights in enumerate(self.w2):
            z = sum(w * hi for w, hi in zip(weights, h)) + self.b2[i]
            out.append(z)
        return out

