from __future__ import annotations

import math
from typing import List


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


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

