from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from ..core.plan_ir import Skill


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
        stage1, stage1_details = self._stage1(
            skill, nominal_inputs, boundary_generator, error_generator
        )
        stage2, stage2_details = self._stage2(skill, pre_condition, post_condition, param_sampler)
        stage3, stage3_details = self._stage3(skill, held_out_tasks, baseline_fn)
        passed = stage1 and stage2 and stage3
        return VerificationReport(
            passed=passed,
            stage1_passed=stage1,
            stage2_passed=stage2,
            stage3_passed=stage3,
            details={
                "stage1": stage1_details,
                "stage2": stage2_details,
                "stage3": stage3_details,
            },
        )

    def _stage1(
        self,
        skill: Skill,
        nominal_inputs: Iterable[Dict[str, Any]],
        boundary_generator: Callable[[], Dict[str, Any]],
        error_generator: Callable[[], Dict[str, Any]],
    ) -> Tuple[bool, Dict[str, Any]]:
        details = {"nominal": 0, "boundary": 0, "error": 0, "failures": []}
        for params in nominal_inputs:
            if not self._safe_exec(skill, params):
                details["failures"].append({"stage": "nominal", "params": params})
                return False, details
            details["nominal"] += 1
        for _ in range(self.config.boundary_cases):
            params = boundary_generator()
            if not self._safe_exec(skill, params):
                details["failures"].append({"stage": "boundary", "params": params})
                return False, details
            details["boundary"] += 1
        for _ in range(self.config.error_cases):
            params = error_generator()
            if not self._safe_exec(skill, params, allow_error=True):
                details["failures"].append({"stage": "error", "params": params})
                return False, details
            details["error"] += 1
        return True, details

    def _stage2(
        self,
        skill: Skill,
        pre_condition: Callable[[Dict[str, Any]], bool],
        post_condition: Callable[[Any], bool],
        param_sampler: Callable[[], Dict[str, Any]],
    ) -> Tuple[bool, Dict[str, Any]]:
        details = {"checked": 0, "violations": 0}
        for _ in range(self.config.randomized_checks):
            params = param_sampler()
            if not pre_condition(params):
                continue
            output = self._safe_exec(skill, params)
            if output is False:
                details["violations"] += 1
                return False, details
            if not post_condition(output):
                details["violations"] += 1
                return False, details
            details["checked"] += 1
        return True, details

    def _stage3(
        self,
        skill: Skill,
        held_out_tasks: Iterable[Dict[str, Any]],
        baseline_fn: Callable[[Dict[str, Any]], bool],
    ) -> Tuple[bool, Dict[str, Any]]:
        details = {"total": 0, "regressions": 0}
        regressions = 0
        total = 0
        for task in held_out_tasks:
            total += 1
            with_skill = self._safe_exec(skill, task, allow_error=True)
            without_skill = baseline_fn(task)
            if (with_skill is False) and without_skill:
                regressions += 1
        if total == 0:
            details["total"] = 0
            return True, details
        delta = regressions / total
        details["total"] = total
        details["regressions"] = regressions
        details["delta"] = delta
        return delta <= self.config.max_regression, details

    def _safe_exec(
        self, skill: Skill, params: Dict[str, Any], allow_error: bool = False
    ) -> Any:
        try:
            return self.exec_fn(skill, params)
        except Exception:
            return allow_error

