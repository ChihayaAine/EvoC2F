"""Skill verification interfaces and convenience helpers."""

from typing import Iterable

from .verification import VerificationConfig, VerificationReport, SkillVerifier


def verify_skill(
    verifier: SkillVerifier,
    skill,
    nominal_inputs: Iterable[dict],
    boundary_generator,
    error_generator,
    pre_condition,
    post_condition,
    param_sampler,
    held_out_tasks: Iterable[dict],
    baseline_fn,
) -> VerificationReport:
    return verifier.verify(
        skill=skill,
        nominal_inputs=nominal_inputs,
        boundary_generator=boundary_generator,
        error_generator=error_generator,
        pre_condition=pre_condition,
        post_condition=post_condition,
        param_sampler=param_sampler,
        held_out_tasks=held_out_tasks,
        baseline_fn=baseline_fn,
    )


__all__ = ["VerificationConfig", "VerificationReport", "SkillVerifier", "verify_skill"]

