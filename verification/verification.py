from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from core.plan_ir import Skill


@dataclass
class VerificationConfig:
    max_regression: float = 0.0
    boundary_cases: int = 10
    error_cases: int = 10
    randomized_checks: int = 50
    max_failures_stage1: int = 0
    min_contract_checks: int = 5
    random_seed: Optional[int] = None


@dataclass
class VerificationReport:
    passed: bool
    stage1_passed: bool
    stage2_passed: bool
    stage3_passed: bool
    details: Dict[str, Any]


@dataclass
class ExecutionOutcome:
    success: bool
    output: Any
    error: Optional[str] = None


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
        error_validator: Optional[Callable[[Dict[str, Any]], bool]] = None,
        contract_checker: Optional[Callable[[Dict[str, Any], Any], bool]] = None,
    ) -> VerificationReport:
        if self.config.random_seed is not None:
            random.seed(self.config.random_seed)
        stage1, stage1_details = self._stage1(
            skill, nominal_inputs, boundary_generator, error_generator, error_validator
        )
        stage2, stage2_details = self._stage2(
            skill, pre_condition, post_condition, param_sampler, contract_checker
        )
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
        error_validator: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        details = {"nominal": 0, "boundary": 0, "error": 0, "failures": []}
        failures = 0
        for params in nominal_inputs:
            outcome = self._safe_exec(skill, params)
            if not outcome.success:
                details["failures"].append({"stage": "nominal", "params": params})
                failures += 1
                if failures > self.config.max_failures_stage1:
                    return False, details
            details["nominal"] += 1
        for _ in range(self.config.boundary_cases):
            params = boundary_generator()
            outcome = self._safe_exec(skill, params)
            if not outcome.success:
                details["failures"].append({"stage": "boundary", "params": params})
                failures += 1
                if failures > self.config.max_failures_stage1:
                    return False, details
            details["boundary"] += 1
        for _ in range(self.config.error_cases):
            params = error_generator()
            outcome = self._safe_exec(skill, params, allow_error=True)
            if not outcome.success:
                valid_error = True
                if error_validator:
                    valid_error = bool(error_validator(params))
                if not valid_error:
                    details["failures"].append({"stage": "error", "params": params})
                    failures += 1
                    if failures > self.config.max_failures_stage1:
                        return False, details
            else:
                # If error cases unexpectedly succeed, require explicit validator approval.
                if error_validator and not error_validator(params):
                    details["failures"].append({"stage": "error", "params": params})
                    failures += 1
                    if failures > self.config.max_failures_stage1:
                        return False, details
            details["error"] += 1
        return True, details

    def _stage2(
        self,
        skill: Skill,
        pre_condition: Callable[[Dict[str, Any]], bool],
        post_condition: Callable[[Any], bool],
        param_sampler: Callable[[], Dict[str, Any]],
        contract_checker: Optional[Callable[[Dict[str, Any], Any], bool]] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        details = {"checked": 0, "violations": 0, "contract_failures": 0}
        for _ in range(self.config.randomized_checks):
            params = param_sampler()
            if not pre_condition(params):
                continue
            outcome = self._safe_exec(skill, params)
            if not outcome.success:
                details["violations"] += 1
                return False, details
            if not post_condition(outcome.output):
                details["violations"] += 1
                return False, details
            if contract_checker and not contract_checker(params, outcome.output):
                details["contract_failures"] += 1
                return False, details
            details["checked"] += 1
        if details["checked"] < self.config.min_contract_checks:
            return False, details
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
        failures = 0
        for task in held_out_tasks:
            total += 1
            outcome = self._safe_exec(skill, task, allow_error=True)
            without_skill = baseline_fn(task)
            if (not outcome.success) and without_skill:
                regressions += 1
            if not outcome.success:
                failures += 1
        if total == 0:
            details["total"] = 0
            return True, details
        delta = regressions / total
        details["total"] = total
        details["regressions"] = regressions
        details["delta"] = delta
        details["failures"] = failures
        return delta <= self.config.max_regression, details

    def _safe_exec(
        self, skill: Skill, params: Dict[str, Any], allow_error: bool = False
    ) -> ExecutionOutcome:
        try:
            return ExecutionOutcome(success=True, output=self.exec_fn(skill, params))
        except Exception as exc:
            if allow_error:
                return ExecutionOutcome(success=False, output=None, error=str(exc))
            return ExecutionOutcome(success=False, output=None, error=str(exc))

