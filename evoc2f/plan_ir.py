from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple


class SideEffect(Enum):
    PURE = "pure"
    READ = "read"
    WRITE = "write"


class Environment(Enum):
    LOCAL = "local"
    EXTERNAL = "external"


@dataclass(frozen=True)
class EffectType:
    side_effect: SideEffect
    environment: Environment

    def dominates(self, other: "EffectType") -> bool:
        return (
            _side_effect_rank(self.side_effect)
            >= _side_effect_rank(other.side_effect)
            and _env_rank(self.environment) >= _env_rank(other.environment)
        )


def _side_effect_rank(se: SideEffect) -> int:
    return {SideEffect.PURE: 0, SideEffect.READ: 1, SideEffect.WRITE: 2}[se]


def _env_rank(env: Environment) -> int:
    return {Environment.LOCAL: 0, Environment.EXTERNAL: 1}[env]


@dataclass(frozen=True)
class ResourceAccess:
    resource: str
    mode: str  # "R" or "W"

    def is_read(self) -> bool:
        return self.mode == "R"

    def is_write(self) -> bool:
        return self.mode == "W"


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int
    backoff_gamma: float
    retry_exceptions: Tuple[type, ...] = ()
    fallback: Optional[Callable[[Exception], Any]] = None


@dataclass
class Tool:
    name: str
    signature: Callable[..., Any]
    effect: EffectType
    resources: Tuple[ResourceAccess, ...]
    expected_latency_ms: float
    expected_cost: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Skill(Tool):
    description: str = ""
    status: str = "shadow"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanNode:
    node_id: str
    func: Tool
    params: Dict[str, Any]
    effect: EffectType
    resources: Tuple[ResourceAccess, ...]
    retry_policy: RetryPolicy
    idempotency_key: Optional[str]
    output_type: Optional[type] = None
    compensation: Optional[Callable[[Any], Any]] = None


@dataclass
class PlanIR:
    nodes: Dict[str, PlanNode]
    data_edges: Set[Tuple[str, str]]
    resource_edges: Set[Tuple[str, str]]
    sync_edges: Set[Tuple[str, str]] = field(default_factory=set)

    def all_edges(self) -> Set[Tuple[str, str]]:
        return set(self.data_edges) | set(self.resource_edges) | set(self.sync_edges)

    def predecessors(self, node_id: str) -> Set[str]:
        return {u for u, v in self.all_edges() if v == node_id}

    def successors(self, node_id: str) -> Set[str]:
        return {v for u, v in self.all_edges() if u == node_id}

    def topological_order(self) -> List[str]:
        order: List[str] = []
        incoming = {n: 0 for n in self.nodes}
        for u, v in self.all_edges():
            incoming[v] += 1
        ready = sorted([n for n, c in incoming.items() if c == 0])
        while ready:
            cur = ready.pop(0)
            order.append(cur)
            for succ in self.successors(cur):
                incoming[succ] -= 1
                if incoming[succ] == 0:
                    ready.append(succ)
                    ready.sort()
        if len(order) != len(self.nodes):
            raise ValueError("Cycle detected in Plan IR")
        return order

    def is_acyclic(self) -> bool:
        try:
            self.topological_order()
            return True
        except ValueError:
            return False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}
        self._resource_overrides: Dict[str, Set[ResourceAccess]] = {}
        self._effect_overrides: Dict[str, EffectType] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def infer_resources(self, tool: Tool) -> Set[ResourceAccess]:
        if tool.name in self._resource_overrides:
            return set(self._resource_overrides[tool.name]) | set(tool.resources)
        return set(tool.resources)

    def infer_effect(self, tool: Tool) -> EffectType:
        if tool.name in self._effect_overrides:
            override = self._effect_overrides[tool.name]
            if override.dominates(tool.effect):
                return override
        return tool.effect

    def expand_from_trace(self, tool_name: str, accessed: Iterable[ResourceAccess]) -> None:
        current = self._resource_overrides.get(tool_name, set())
        expanded = current | set(accessed)
        self._resource_overrides[tool_name] = expanded

    def conservative_default(self, tool: Tool) -> Tool:
        effect = tool.effect
        if effect is None:
            effect = EffectType(SideEffect.WRITE, Environment.EXTERNAL)
        return Tool(
            name=tool.name,
            signature=tool.signature,
            effect=effect,
            resources=tool.resources,
            expected_latency_ms=tool.expected_latency_ms,
            expected_cost=tool.expected_cost,
            metadata=tool.metadata,
        )


def build_plan_ir(
    nodes: Sequence[PlanNode],
    registry: ToolRegistry,
    type_checker: Optional[Callable[[Optional[type], Optional[type]], bool]] = None,
) -> PlanIR:
    node_map = {n.node_id: n for n in nodes}
    data_edges: Set[Tuple[str, str]] = set()
    for node in nodes:
        for value in node.params.values():
            if isinstance(value, dict) and value.get("ref"):
                ref_node_id = value["ref"][0]
                data_edges.add((ref_node_id, node.node_id))
    data_order = _topological_order_from_edges(node_map.keys(), data_edges)
    resource_edges = _build_resource_edges(node_map, data_order, registry)
    plan = PlanIR(nodes=node_map, data_edges=data_edges, resource_edges=resource_edges)
    if not check_semantic_consistency(plan, registry, type_checker):
        raise ValueError("Semantic consistency check failed")
    return plan


def _topological_order_from_edges(nodes: Iterable[str], edges: Set[Tuple[str, str]]) -> List[str]:
    incoming = {n: 0 for n in nodes}
    successors: Dict[str, List[str]] = {n: [] for n in nodes}
    for u, v in edges:
        incoming[v] += 1
        successors[u].append(v)
    ready = sorted([n for n, c in incoming.items() if c == 0])
    order = []
    while ready:
        cur = ready.pop(0)
        order.append(cur)
        for succ in sorted(successors[cur]):
            incoming[succ] -= 1
            if incoming[succ] == 0:
                ready.append(succ)
                ready.sort()
    if len(order) != len(incoming):
        raise ValueError("Cycle detected in dependency graph")
    return order


def _build_resource_edges(
    nodes: Dict[str, PlanNode],
    data_order: List[str],
    registry: ToolRegistry,
) -> Set[Tuple[str, str]]:
    ordering = {node_id: idx for idx, node_id in enumerate(data_order)}
    resource_edges: Set[Tuple[str, str]] = set()
    for u_id, u in nodes.items():
        for v_id, v in nodes.items():
            if u_id == v_id:
                continue
            if ordering[u_id] >= ordering[v_id]:
                continue
            if _resource_conflict(u, v, registry):
                resource_edges.add((u_id, v_id))
    return resource_edges


def _resource_conflict(u: PlanNode, v: PlanNode, registry: ToolRegistry) -> bool:
    u_res = registry.infer_resources(u.func)
    v_res = registry.infer_resources(v.func)
    for ru in u_res:
        for rv in v_res:
            if ru.resource != rv.resource:
                continue
            if ru.mode != rv.mode and ("W" in (ru.mode, rv.mode)):
                return True
    return False


def check_semantic_consistency(
    plan: PlanIR,
    registry: ToolRegistry,
    type_checker: Optional[Callable[[Optional[type], Optional[type]], bool]] = None,
) -> bool:
    if not plan.is_acyclic():
        return False
    if type_checker is None:
        type_checker = lambda out_t, in_t: True
    for u, v in plan.data_edges:
        if not type_checker(plan.nodes[u].output_type, plan.nodes[v].output_type):
            return False
    for node in plan.nodes.values():
        inferred = registry.infer_resources(node.func)
        if not set(node.resources).issuperset(inferred):
            return False
        if not node.effect.dominates(registry.infer_effect(node.func)):
            return False
        if node.effect.side_effect != SideEffect.PURE and not node.idempotency_key:
            return False
    return True

