from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from core.plan_ir import PlanIR, PlanNode, Skill
from skills.manager import SkillManager
from verification.verification import SkillVerifier, VerificationReport


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
    dataflow: List[Dict[str, Any]] = field(default_factory=list)


class CandidateExtractor:
    def __init__(self, min_support: float = 0.1, min_len: int = 2, max_len: int = 8) -> None:
        self.min_support = min_support
        self.min_len = min_len
        self.max_len = max_len

    def extract(self, traces: Sequence[Trace]) -> List[CandidateSkill]:
        sequences = [trace.to_sequence() for trace in traces]
        patterns = prefixspan(sequences, self.min_support)
        candidates: List[CandidateSkill] = []
        for pattern, support in patterns:
            if len(pattern) < self.min_len or len(pattern) > self.max_len:
                continue
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
        return [self._node_signature(plan.nodes[node_id]) for node_id in plan.topological_order()]

    def canonicalize_with_dataflow(self, plan: PlanIR) -> List[Dict[str, Any]]:
        linear = []
        for node_id in plan.topological_order():
            node = plan.nodes[node_id]
            linear.append(
                {
                    "tool": node.func.name,
                    "inputs": sorted(list(self._collect_ref_fields(node))),
                    "effect": node.effect.side_effect.value,
                }
            )
        return linear

    def extract_from_plans(self, plans: Sequence[PlanIR]) -> List[CandidateSkill]:
        traces = [Trace(nodes=[{"tool": name} for name in self.canonicalize(plan)]) for plan in plans]
        return self.extract(traces)

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

    def _node_signature(self, node: PlanNode) -> str:
        effect = node.effect.side_effect.value
        env = node.effect.environment.value
        return f"{node.func.name}:{effect}:{env}"

    def _collect_ref_fields(self, node: PlanNode) -> List[str]:
        fields: List[str] = []
        for value in node.params.values():
            if isinstance(value, dict) and value.get("ref"):
                ref = value["ref"]
                if isinstance(ref, (list, tuple)) and len(ref) > 1:
                    fields.append(str(ref[1]))
        return fields


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

    def pairwise_margin(self, score_pos: float, score_neg: float) -> float:
        return score_pos - score_neg

    def preference_weight(self, margin: float, temperature: float = 1.0) -> float:
        import math

        return 1.0 / (1.0 + math.exp(-margin / max(temperature, 1e-6)))


@dataclass
class SkillEvolutionConfig:
    min_support: float = 0.1
    min_len: int = 2
    max_len: int = 8
    max_candidates: int = 50
    verification_required: bool = True


@dataclass
class SkillEvolutionResult:
    admitted: List[str]
    rejected: Dict[str, str]
    reports: Dict[str, VerificationReport]


class SkillEvolutionEngine:
    def __init__(
        self,
        skill_manager: SkillManager,
        verifier: Optional[SkillVerifier] = None,
        extractor: Optional[CandidateExtractor] = None,
        config: Optional[SkillEvolutionConfig] = None,
    ) -> None:
        self.skill_manager = skill_manager
        self.verifier = verifier or SkillVerifier()
        self.extractor = extractor or CandidateExtractor()
        self.config = config or SkillEvolutionConfig()

    def evolve(
        self,
        plans: Sequence[PlanIR],
        skill_factory: Callable[[CandidateSkill], Skill],
        verification_inputs: Dict[str, Any],
    ) -> SkillEvolutionResult:
        candidates = self.extractor.extract_from_plans(plans)
        candidates = sorted(candidates, key=lambda c: c.support, reverse=True)[
            : self.config.max_candidates
        ]
        admitted: List[str] = []
        rejected: Dict[str, str] = {}
        reports: Dict[str, VerificationReport] = {}
        for cand in candidates:
            skill = skill_factory(cand)
            skill.metadata.setdefault("support", cand.support)
            skill.metadata.setdefault("template", cand.template)
            if self.config.verification_required:
                report = self._verify(skill, verification_inputs)
                reports[skill.name] = report
                if not report.passed:
                    rejected[skill.name] = "verification_failed"
                    continue
            self.skill_manager.library.add(skill)
            self.skill_manager.shadow(skill.name)
            admitted.append(skill.name)
        return SkillEvolutionResult(admitted=admitted, rejected=rejected, reports=reports)

    def _verify(self, skill: Skill, verification_inputs: Dict[str, Any]) -> VerificationReport:
        return self.verifier.verify(
            skill=skill,
            nominal_inputs=verification_inputs["nominal_inputs"],
            boundary_generator=verification_inputs["boundary_generator"],
            error_generator=verification_inputs["error_generator"],
            pre_condition=verification_inputs["pre_condition"],
            post_condition=verification_inputs["post_condition"],
            param_sampler=verification_inputs["param_sampler"],
            held_out_tasks=verification_inputs["held_out_tasks"],
            baseline_fn=verification_inputs["baseline_fn"],
        )

