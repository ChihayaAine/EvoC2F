from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..core.plan_ir import PlanIR


@dataclass
class Trace:
    nodes: List[Dict[str, Any]]

    def to_sequence(self) -> List[str]:
        return [node["tool"] for node in self.nodes]


@dataclass
class CandidateSkill:
    pattern: List[str]
    support: float
    template: List[str]
    constraints: Dict[str, Any] = field(default_factory=dict)


class CandidateExtractor:
    def __init__(self, min_support: float = 0.1) -> None:
        self.min_support = min_support

    def extract(self, traces: Sequence[Trace]) -> List[CandidateSkill]:
        sequences = [trace.to_sequence() for trace in traces]
        patterns = prefixspan(sequences, self.min_support)
        candidates: List[CandidateSkill] = []
        for pattern, support in patterns:
            constraints = {
                "type_constraints": [],
                "contracts": [],
                "min_support": support,
            }
            candidates.append(
                CandidateSkill(
                    pattern=pattern,
                    support=support,
                    template=list(pattern),
                    constraints=constraints,
                )
            )
        return self._merge_templates(candidates)

    def anti_unify(self, a: List[str], b: List[str]) -> List[str]:
        length = max(len(a), len(b))
        template: List[str] = []
        for i in range(length):
            token_a = a[i] if i < len(a) else None
            token_b = b[i] if i < len(b) else None
            if token_a == token_b:
                template.append(token_a)
            else:
                template.append("*")
        return template

    def canonicalize(self, plan: PlanIR) -> List[str]:
        return [plan.nodes[node_id].func.name for node_id in plan.topological_order()]

    def _merge_templates(self, candidates: List[CandidateSkill]) -> List[CandidateSkill]:
        merged: List[CandidateSkill] = []
        for cand in candidates:
            matched = False
            for existing in merged:
                if len(existing.template) != len(cand.template):
                    continue
                template = self.anti_unify(existing.template, cand.template)
                if "*" not in template:
                    existing.support = max(existing.support, cand.support)
                    matched = True
                    break
                similarity = self._template_similarity(existing.template, cand.template)
                if similarity >= 0.6:
                    existing.template = template
                    existing.support = max(existing.support, cand.support)
                    matched = True
                    break
            if not matched:
                merged.append(cand)
        return merged

    def _template_similarity(self, a: List[str], b: List[str]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        matches = sum(1 for x, y in zip(a, b) if x == y)
        return matches / len(a)


def prefixspan(sequences: Sequence[List[str]], min_support: float) -> List[Tuple[List[str], float]]:
    total = len(sequences)
    patterns: List[Tuple[List[str], float]] = []

    def _frequent_items(prefix: List[str], projected: List[List[str]]) -> None:
        counts: Dict[str, int] = {}
        for seq in projected:
            used = set()
            for item in seq:
                if item in used:
                    continue
                counts[item] = counts.get(item, 0) + 1
                used.add(item)
        for item, count in counts.items():
            support = count / total
            if support >= min_support:
                new_prefix = prefix + [item]
                patterns.append((new_prefix, support))
                new_projected = []
                for seq in projected:
                    if item in seq:
                        idx = seq.index(item)
                        suffix = seq[idx + 1 :]
                        if suffix:
                            new_projected.append(suffix)
                if new_projected:
                    _frequent_items(new_prefix, new_projected)

    _frequent_items([], sequences)
    return patterns


class PreferenceLearner:
    def __init__(self, beta: float = 0.1) -> None:
        self.beta = beta

    def dpo_loss(
        self,
        logp_pos: float,
        logp_neg: float,
        logp_ref_pos: float,
        logp_ref_neg: float,
    ) -> float:
        import math

        term = self.beta * (logp_pos - logp_ref_pos) - self.beta * (logp_neg - logp_ref_neg)
        return -math.log(1 / (1 + math.exp(-term)))

