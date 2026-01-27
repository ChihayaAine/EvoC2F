from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .plan_ir import (
    EffectType,
    PlanIR,
    PlanNode,
    RetryPolicy,
    Tool,
    ToolRegistry,
    build_plan_ir,
)
from .skills import SkillLibrary
from .utils import cosine_similarity, MLP


@dataclass
class PlannerConfig:
    top_k_skills: int = 5
    default_retry: RetryPolicy = RetryPolicy(max_retries=2, backoff_gamma=2.0)


class SkillAugmentedPlanner:
    def __init__(
        self,
        registry: ToolRegistry,
        library: SkillLibrary,
        config: Optional[PlannerConfig] = None,
    ) -> None:
        self.registry = registry
        self.library = library
        self.config = config or PlannerConfig()
        self.router = MLP(input_dim=4, hidden_dim=8, output_dim=1)

    def retrieve_skills(
        self, query_embedding: List[float], skill_embeddings: Dict[str, List[float]]
    ) -> List[Tool]:
        scored: List[Tuple[float, Tool]] = []
        for skill in self.library.active_skills():
            embedding = skill_embeddings.get(skill.name, [])
            if not embedding or not query_embedding:
                semantic = 0.0
            else:
                semantic = cosine_similarity(embedding, query_embedding)
            metrics = self.library.metrics.get(skill.name)
            learned = self.router.forward(
                [
                    metrics.success_rate if metrics else 1.0,
                    metrics.avg_cost if metrics else 0.0,
                    metrics.last_used_ts if metrics else 0.0,
                    float(metrics.usage_count if metrics else 0.0),
                ]
            )[0]
            score = semantic + learned
            scored.append((score, skill))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [tool for _, tool in scored[: self.config.top_k_skills]]

    def generate_plan(
        self,
        task: str,
        tools: Sequence[Tool],
        params: Sequence[Dict[str, Any]],
        idempotency_keys: Sequence[Optional[str]],
    ) -> PlanIR:
        nodes: List[PlanNode] = []
        for idx, tool in enumerate(tools):
            node_id = f"v{idx}"
            node = PlanNode(
                node_id=node_id,
                func=tool,
                params=params[idx],
                effect=tool.effect,
                resources=tool.resources,
                retry_policy=self.config.default_retry,
                idempotency_key=idempotency_keys[idx],
                output_type=None,
                compensation=tool.metadata.get("compensate"),
            )
            nodes.append(node)
        return build_plan_ir(nodes, self.registry)

