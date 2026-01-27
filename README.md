# EvoC2F

EvoC2F (Evolving Compilable Code Framework) is a reference implementation of the
paper method: a constrained Plan IR, a semantic compiler with rate limiting and
fault tolerance, and a verification-gated skill evolution pipeline.

## Structure

- `evoc2f/plan_ir.py`: Plan IR, tools, semantic consistency, annotations
- `evoc2f/compiler.py`: semantic compiler, DAG scheduling, penalties
- `evoc2f/runtime.py`: executor with locks, token buckets, circuit breakers, saga compensation
- `evoc2f/skills.py`: skill library lifecycle (shadow/canary/stable)
- `evoc2f/planner.py`: skill-augmented planner and retrieval scoring
- `evoc2f/learning.py`: trace mining, PrefixSpan, anti-unification, DPO loss
- `evoc2f/verification.py`: three-stage verification pipeline

## Minimal Usage

```python
from evoc2f import (
    Tool, Skill, EffectType, ResourceAccess, RetryPolicy, ToolRegistry,
    PlannerConfig, SkillAugmentedPlanner, SemanticCompiler, CompilerConfig,
    Executor, ExecutionConfig, SideEffect, Environment, SkillLibrary
)

def fetch_data(query: str) -> dict:
    return {"value": query}

tool = Tool(
    name="fetch",
    signature=fetch_data,
    effect=EffectType(side_effect=SideEffect.READ, environment=Environment.EXTERNAL),
    resources=(ResourceAccess("api.search", "R"),),
    expected_latency_ms=120,
    expected_cost=0.01,
)
registry = ToolRegistry()
registry.register(tool)

planner = SkillAugmentedPlanner(registry, library=SkillLibrary(), config=PlannerConfig())
plan = planner.generate_plan(
    task="search",
    tools=[tool],
    params=[{"query": "hello"}],
    idempotency_keys=[None],
)

compiler = SemanticCompiler(
    registry,
    CompilerConfig(concurrency_limit=4, deadline_ms=10000, rate_limits={"api.search": 10}),
)
compiled = compiler.compile(plan)

executor = Executor(registry, rate_limits={"api.search": 10}, config=ExecutionConfig(concurrency_limit=4))
result = executor.execute(compiled)
print(result.outputs)
```
