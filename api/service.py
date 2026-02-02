from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Dict, List, Optional

from core.compiler import CompilerConfig, SemanticCompiler
from core.plan_ir import PlanIR, Skill, ToolRegistry
from schemas.plan_schema import PlanSchemaValidator
from tracing.tracer import Tracer
from planning.planner import PlannerConfig, SkillAugmentedPlanner
from runtime.executor import ExecutionConfig, Executor
from skills.skills import SkillLibrary
from metrics.tracker import MetricTracker
from tracing.exporter import TraceExporter


@dataclass
class ServiceConfig:
    compiler: CompilerConfig
    executor: ExecutionConfig
    planner: PlannerConfig


class EvoC2FService:
    def __init__(self, registry: ToolRegistry, skills: SkillLibrary, config: ServiceConfig) -> None:
        self.registry = registry
        self.skills = skills
        self.planner = SkillAugmentedPlanner(registry, skills, config.planner)
        self.compiler = SemanticCompiler(registry, config.compiler)
        self.executor = Executor(registry, config=config.executor)
        self.tracer = Tracer()
        self.metrics = MetricTracker()
        self.exporter = TraceExporter()
        self.plan_validator = PlanSchemaValidator()

    def run(self, plan: PlanIR) -> Dict[str, Any]:
        start = perf_counter()
        self.tracer.event("plan_received", {"nodes": len(plan.nodes)})
        try:
            compiled = self.compiler.compile(plan)
        except Exception as exc:
            self.tracer.event("plan_compile_failed", {"error": str(exc)})
            raise
        self.tracer.event(
            "plan_compiled",
            {"critical_path_ms": compiled.critical_path_ms, "slack": compiled.slack},
        )
        result = self.executor.execute(compiled)
        self.tracer.event(
            "plan_executed",
            {"failures": len(result.failures), "duration_ms": result.duration_ms},
        )
        self._record_skill_metrics(plan, result)
        self.metrics.inc("plans_total", 1)
        if result.failures:
            self.metrics.inc("plans_failed", 1)
        self.metrics.observe("plan_latency_ms", (perf_counter() - start) * 1000)
        return result.outputs

    def run_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        errors = self.plan_validator.validate(payload)
        if errors:
            raise ValueError("; ".join(errors))
        plan = PlanIR.from_dict(payload, self.registry)
        return self.run(plan)

    def run_with_trace(self, plan: PlanIR) -> Dict[str, Any]:
        outputs = self.run(plan)
        return {"outputs": outputs, "trace": self.tracer.store.list()}

    def run_with_report(self, plan: PlanIR) -> Dict[str, Any]:
        outputs = self.run(plan)
        trace_payload = self.exporter.export_dict(self.tracer.store)
        metrics = {
            "plans_total": self.metrics.counters.get("plans_total", 0),
            "plans_failed": self.metrics.counters.get("plans_failed", 0),
            "plan_latency_ms": self.metrics.summary("plan_latency_ms"),
        }
        return {"outputs": outputs, "trace": trace_payload, "metrics": metrics}

    def run_payload_with_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        errors = self.plan_validator.validate(payload)
        if errors:
            return {"outputs": {}, "errors": errors}
        plan = PlanIR.from_dict(payload, self.registry)
        outputs = self.run(plan)
        trace_payload = self.exporter.export_dict(self.tracer.store)
        metrics = {
            "plans_total": self.metrics.counters.get("plans_total", 0),
            "plans_failed": self.metrics.counters.get("plans_failed", 0),
            "plan_latency_ms": self.metrics.summary("plan_latency_ms"),
        }
        return {"outputs": outputs, "trace": trace_payload, "metrics": metrics}

    def _record_skill_metrics(self, plan: PlanIR, result: Any) -> None:
        ts = perf_counter()
        for node_id, node in plan.nodes.items():
            if not isinstance(node.func, Skill):
                continue
            success = node_id not in result.failures
            cost = node.func.expected_cost
            self.skills.record_usage(node.func.name, success=success, cost=cost, ts=ts)

