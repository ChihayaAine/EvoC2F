"""EvoC2F: Evolving Compilable Code Framework."""

__version__ = "0.1.0"

from .core.plan_ir import (
    SideEffect,
    Environment,
    EffectType,
    ResourceAccess,
    RetryPolicy,
    Tool,
    Skill,
    PlanNode,
    PlanIR,
    ToolRegistry,
)
from .core.compiler import (
    CompilerConfig,
    CompiledPlan,
    SemanticCompiler,
)
from .runtime.executor import (
    ExecutionConfig,
    ExecutionResult,
    Executor,
)
from .skills.skills import (
    SkillLibrary,
    SkillStatus,
)
from .planning.planner import (
    PlannerConfig,
    SkillAugmentedPlanner,
)
from .configs.defaults import Defaults, RuntimeLimits
from .api.service import EvoC2FService, ServiceConfig
from .verification.verification import (
    VerificationConfig,
    VerificationReport,
    SkillVerifier,
)
from .learning.learning import (
    Trace,
    CandidateExtractor,
    PreferenceLearner,
)

__all__ = [
    "__version__",
    "SideEffect",
    "Environment",
    "EffectType",
    "ResourceAccess",
    "RetryPolicy",
    "Tool",
    "Skill",
    "PlanNode",
    "PlanIR",
    "ToolRegistry",
    "CompilerConfig",
    "CompiledPlan",
    "SemanticCompiler",
    "ExecutionConfig",
    "ExecutionResult",
    "Executor",
    "SkillLibrary",
    "SkillStatus",
    "PlannerConfig",
    "SkillAugmentedPlanner",
    "Defaults",
    "RuntimeLimits",
    "EvoC2FService",
    "ServiceConfig",
    "VerificationConfig",
    "VerificationReport",
    "SkillVerifier",
    "Trace",
    "CandidateExtractor",
    "PreferenceLearner",
]


def build_service(registry: ToolRegistry, skills: SkillLibrary) -> EvoC2FService:
    defaults = Defaults()
    limits = RuntimeLimits()
    config = ServiceConfig(
        compiler=defaults.compiler(limits),
        executor=defaults.executor(limits),
        planner=defaults.planner(),
    )
    return EvoC2FService(registry=registry, skills=skills, config=config)

