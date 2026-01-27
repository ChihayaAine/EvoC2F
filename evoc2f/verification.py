from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .plan_ir import Skill


@dataclass
class VerificationConfig:
    max_regression: float = 0.0
    boundary_cases: int = 10
    error_cases: int = 10
    randomized_checks: int = 50


@dataclass
class VerificationReport:
    passed: bool
    stage1_passed: bool
    stage2_passed: bool
    stage3_passed: bool
    details: Dict[str, Any]


class SkillVerifier:
    def __init__(
        self,
        config: Optional[VerificationConfig] = None,
        exec_fn: Optional[Callable[[Skill, Dict[str, Any]], Any]] = None,
    ) -> None:
        self.config = config or VerificationConfig()
        self.exec_fn = exec_fn or (lambda skill, params: skill.signature(**params))

    def verify(
        self,
        skill: Skill,
        nominal_inputs: Iterable[Dict[str, Any]],
        boundary_generator: Callable[[], Dict[str, Any]],
        error_generator: Callable[[], Dict[str, Any]],
        pre_condition: Callable[[Dict[str, Any]], bool],
        post_condition: Callable[[Any], bool],
        param_sampler: Callable[[], Dict[str, Any]],
        held_out_tasks: Iterable[Dict[str, Any]],
        baseline_fn: Callable[[Dict[str, Any]], bool],
    ) -> VerificationReport:
        stage1 = self._stage1(skill, nominal_inputs, boundary_generator, error_generator)
        stage2 = self._stage2(skill, pre_condition, post_condition, param_sampler)
        stage3 = self._stage3(skill, held_out_tasks, baseline_fn)
        passed = stage1 and stage2 and stage3
        return VerificationReport(
            passed=passed,
            stage1_passed=stage1,
            stage2_passed=stage2,
            stage3_passed=stage3,
            details={},
        )

    def _stage1(
        self,
        skill: Skill,
        nominal_inputs: Iterable[Dict[str, Any]],
        boundary_generator: Callable[[], Dict[str, Any]],
        error_generator: Callable[[], Dict[str, Any]],
    ) -> bool:
        for params in nominal_inputs:
            if not self._safe_exec(skill, params):
                return False
        for _ in range(self.config.boundary_cases):
            if not self._safe_exec(skill, boundary_generator()):
                return False
        for _ in range(self.config.error_cases):
            if not self._safe_exec(skill, error_generator(), allow_error=True):
                return False
        return True

    def _stage2(
        self,
        skill: Skill,
        pre_condition: Callable[[Dict[str, Any]], bool],
        post_condition: Callable[[Any], bool],
        param_sampler: Callable[[], Dict[str, Any]],
    ) -> bool:
        for _ in range(self.config.randomized_checks):
            params = param_sampler()
            if not pre_condition(params):
                continue
            output = self._safe_exec(skill, params)
            if output is False:
                return False
            if not post_condition(output):
                return False
        return True

    def _stage3(
        self,
        skill: Skill,
        held_out_tasks: Iterable[Dict[str, Any]],
        baseline_fn: Callable[[Dict[str, Any]], bool],
    ) -> bool:
        regressions = 0
        total = 0
        for task in held_out_tasks:
            total += 1
            with_skill = self._safe_exec(skill, task, allow_error=True)
            without_skill = baseline_fn(task)
            if (with_skill is False) and without_skill:
                regressions += 1
        if total == 0:
            return True
        delta = regressions / total
        return delta <= self.config.max_regression

    def _safe_exec(
        self, skill: Skill, params: Dict[str, Any], allow_error: bool = False
    ) -> Any:
        try:
            return self.exec_fn(skill, params)
        except Exception:
            return allow_error

