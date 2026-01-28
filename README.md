# EvoC2F

EvoC2F (Evolving Compilable Code Framework) is a reference implementation of the
paper method: a constrained Plan IR, a semantic compiler with rate limiting and
fault tolerance, and a verification-gated skill evolution pipeline.

## Structure

- `evoc2f/core/plan_ir.py`: Plan IR, tools, semantic consistency, annotations
- `evoc2f/core/compiler.py`: semantic compiler, DAG scheduling, penalties
- `evoc2f/runtime/executor.py`: executor with locks, token buckets, circuit breakers, saga compensation
- `evoc2f/skills/skills.py`: skill library lifecycle (shadow/canary/stable)
- `evoc2f/planning/planner.py`: skill-augmented planner and retrieval scoring
- `evoc2f/learning/learning.py`: trace mining, PrefixSpan, anti-unification, DPO loss
- `evoc2f/verification/verification.py`: three-stage verification pipeline
- `evoc2f/tools/base.py`: tool schema and wrappers (non-core)
- `evoc2f/envs/base.py`: environment interfaces (non-core)
- `evoc2f/tasks/base.py`: task specs and runners (non-core)
- `evoc2f/configs/defaults.py`: default limits and knobs (non-core)
- `evoc2f/scripts/cli.py`: lightweight CLI entrypoint (non-core)
- `evoc2f/datasets/loader.py`: jsonl dataset loader (non-core)
- `evoc2f/eval/runner.py`: evaluation harness (non-core)
- `evoc2f/models/`: model adapters and stubs (non-core)
- `evoc2f/prompts/templates/`: prompt templates for planning and verification
- `evoc2f/prompts/loader.py`: prompt loading helper
- `evoc2f/tracing/`: trace events and tracer utilities
- `evoc2f/registry/`: tool registry helpers
- `evoc2f/memory/`: experience buffer for offline learning
- `evoc2f/storage/`: lightweight JSON store
- `evoc2f/metrics/`: counters and gauges
- `evoc2f/schemas/`: schema validator helpers
- `evoc2f/api/`: service wrapper for plan execution
- `evoc2f/policies/`: gating policies for verification
- `evoc2f/skills/manager.py`: skill lifecycle manager and gating
- `evoc2f/tracing/exporter.py`: trace export utilities

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
