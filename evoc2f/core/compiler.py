from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .plan_ir import PlanIR, PlanNode, ResourceAccess, ToolRegistry


@dataclass
class CompilerConfig:
    concurrency_limit: int
    deadline_ms: float
    rate_limits: Dict[str, float] = field(default_factory=dict)
    rate_bursts: Dict[str, float] = field(default_factory=dict)


@dataclass
class ScheduledNode:
    node_id: str
    start_ms: float
    end_ms: float


@dataclass
class CompiledPlan:
    plan: PlanIR
    schedule: Dict[str, ScheduledNode]
    critical_path_ms: float
    est: Dict[str, float] = field(default_factory=dict)
    lst: Dict[str, float] = field(default_factory=dict)
    slack: Dict[str, float] = field(default_factory=dict)
    rate_penalty: float = 0.0
    retry_penalty: float = 0.0


class SemanticCompiler:
    def __init__(self, registry: ToolRegistry, config: CompilerConfig) -> None:
        self.registry = registry
        self.config = config

    def compile(self, plan: PlanIR) -> CompiledPlan:
        plan.sync_edges = self._build_sync_edges(plan)
        order = plan.topological_order()
        est, lst, critical_path = self._compute_est_lst(plan, order)
        schedule = self._schedule(plan, order)
        slack = {n: lst[n] - est[n] for n in plan.nodes}
        rate_penalty = self._rate_penalty(plan, schedule)
        retry_penalty = self._retry_penalty(plan)
        return CompiledPlan(
            plan=plan,
            schedule=schedule,
            critical_path_ms=critical_path,
            est=est,
            lst=lst,
            slack=slack,
            rate_penalty=rate_penalty,
            retry_penalty=retry_penalty,
        )

    def _build_sync_edges(self, plan: PlanIR) -> Set[Tuple[str, str]]:
        sync_edges: Set[Tuple[str, str]] = set()
        data_order = plan.topological_order()
        order_idx = {node_id: idx for idx, node_id in enumerate(data_order)}
        resources = self._write_resources(plan)
        for resource, nodes in resources.items():
            nodes = sorted(nodes, key=lambda n: order_idx[n])
            for prev, nxt in zip(nodes, nodes[1:]):
                sync_edges.add((prev, nxt))
        return sync_edges

    def _write_resources(self, plan: PlanIR) -> Dict[str, List[str]]:
        writes: Dict[str, List[str]] = {}
        for node in plan.nodes.values():
            for access in node.resources:
                if access.mode == "W":
                    writes.setdefault(access.resource, []).append(node.node_id)
        return writes

    def _compute_est_lst(
        self, plan: PlanIR, order: List[str]
    ) -> Tuple[Dict[str, float], Dict[str, float], float]:
        est: Dict[str, float] = {node_id: 0.0 for node_id in plan.nodes}
        for node_id in order:
            preds = plan.predecessors(node_id)
            if preds:
                est[node_id] = max(
                    est[p] + plan.nodes[p].func.expected_latency_ms for p in preds
                )
        critical = max(
            est[node_id] + plan.nodes[node_id].func.expected_latency_ms for node_id in order
        )
        lst: Dict[str, float] = {
            node_id: critical - plan.nodes[node_id].func.expected_latency_ms
            for node_id in plan.nodes
        }
        for node_id in reversed(order):
            succs = plan.successors(node_id)
            if succs:
                lst[node_id] = min(
                    lst[s] - plan.nodes[node_id].func.expected_latency_ms for s in succs
                )
        return est, lst, critical

    def _schedule(self, plan: PlanIR, order: List[str]) -> Dict[str, ScheduledNode]:
        buckets = self._init_token_buckets(plan)
        schedule: Dict[str, ScheduledNode] = {}
        rank = self._upward_rank(plan)
        unscheduled = set(order)
        backoff_ms = 1.0
        while unscheduled:
            progress = False
            candidates = sorted(unscheduled, key=lambda n: rank[n], reverse=True)
            for node_id in candidates:
                preds = plan.predecessors(node_id)
                if any(pred not in schedule for pred in preds):
                    continue
                earliest = 0.0
                if preds:
                    earliest = max(schedule[p].end_ms for p in preds)
                start_time = self._find_feasible_start(
                    plan, node_id, earliest, schedule, buckets
                )
                if start_time is None:
                    continue
                duration = plan.nodes[node_id].func.expected_latency_ms
                schedule[node_id] = ScheduledNode(
                    node_id=node_id,
                    start_ms=start_time,
                    end_ms=start_time + duration,
                )
                self._reserve_rate_tokens(plan.nodes[node_id], start_time, buckets)
                unscheduled.remove(node_id)
                progress = True
                break
            if not progress:
                backoff_ms *= 2
                if backoff_ms > self.config.deadline_ms:
                    raise RuntimeError("Unable to find feasible schedule under constraints")
                for node_id in list(unscheduled):
                    if plan.predecessors(node_id):
                        continue
                    start_time = self._find_feasible_start(
                        plan, node_id, backoff_ms, schedule, buckets
                    )
                    if start_time is not None:
                        duration = plan.nodes[node_id].func.expected_latency_ms
                        schedule[node_id] = ScheduledNode(
                            node_id=node_id,
                            start_ms=start_time,
                            end_ms=start_time + duration,
                        )
                        self._reserve_rate_tokens(plan.nodes[node_id], start_time, buckets)
                        unscheduled.remove(node_id)
                        progress = True
                if not progress:
                    raise RuntimeError("Unable to find feasible schedule under constraints")
        return schedule

    def _upward_rank(self, plan: PlanIR) -> Dict[str, float]:
        order = list(reversed(plan.topological_order()))
        rank: Dict[str, float] = {node_id: 0.0 for node_id in plan.nodes}
        for node_id in order:
            succs = plan.successors(node_id)
            if succs:
                rank[node_id] = plan.nodes[node_id].func.expected_latency_ms + max(
                    rank[s] for s in succs
                )
            else:
                rank[node_id] = plan.nodes[node_id].func.expected_latency_ms
        return rank

    def _init_token_buckets(self, plan: PlanIR) -> Dict[str, TokenBucket]:
        buckets: Dict[str, TokenBucket] = {}
        for node in plan.nodes.values():
            for access in node.resources:
                if access.resource in self.config.rate_limits:
                    limit_per_sec = self.config.rate_limits[access.resource]
                    rate_per_ms = limit_per_sec / 1000.0
                    burst = self.config.rate_bursts.get(access.resource, limit_per_sec)
                    buckets[access.resource] = TokenBucket(rate_per_ms, burst)
        return buckets

    def _find_feasible_start(
        self,
        plan: PlanIR,
        node_id: str,
        earliest: float,
        schedule: Dict[str, ScheduledNode],
        buckets: Dict[str, "TokenBucket"],
    ) -> Optional[float]:
        node = plan.nodes[node_id]
        start = earliest
        backoff = 1.0
        while start <= self.config.deadline_ms:
            if not self._respects_concurrency(start, node.func.expected_latency_ms, schedule):
                start += backoff
                backoff *= 2
                continue
            if not self._respects_resource_conflicts(plan, node, start, schedule):
                start += backoff
                backoff *= 2
                continue
            if not self._respects_rate_limits(node, start, buckets):
                start += backoff
                backoff *= 2
                continue
            return start
        return None

    def _respects_concurrency(
        self, start: float, duration: float, schedule: Dict[str, ScheduledNode]
    ) -> bool:
        end = start + duration
        active = 0
        for item in schedule.values():
            if self._interval_overlap(start, end, item.start_ms, item.end_ms):
                active += 1
        return active < self.config.concurrency_limit

    def _respects_resource_conflicts(
        self, plan: PlanIR, node: PlanNode, start: float, schedule: Dict[str, ScheduledNode]
    ) -> bool:
        duration = node.func.expected_latency_ms
        end = start + duration
        for scheduled in schedule.values():
            if not self._interval_overlap(start, end, scheduled.start_ms, scheduled.end_ms):
                continue
            other = plan.nodes[scheduled.node_id]
            if _conflict(node.resources, other.resources):
                return False
        return True

    def _interval_overlap(self, a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
        return a_start < b_end and b_start < a_end

    def _respects_rate_limits(
        self, node: PlanNode, start: float, buckets: Dict[str, "TokenBucket"]
    ) -> bool:
        for access in node.resources:
            bucket = buckets.get(access.resource)
            if bucket and not bucket.has_token_at(start):
                return False
        return True

    def _reserve_rate_tokens(
        self, node: PlanNode, start: float, buckets: Dict[str, "TokenBucket"]
    ) -> None:
        for access in node.resources:
            bucket = buckets.get(access.resource)
            if bucket:
                bucket.consume_at(start)

    def _rate_penalty(self, plan: PlanIR, schedule: Dict[str, ScheduledNode]) -> float:
        window_ms = 1000.0
        penalty = 0.0
        for resource, limit in self.config.rate_limits.items():
            times = sorted(
                scheduled.start_ms
                for scheduled in schedule.values()
                if any(
                    access.resource == resource
                    for access in plan.nodes[scheduled.node_id].resources
                )
            )
            for i, t in enumerate(times):
                window_end = t + window_ms
                count = sum(1 for t2 in times[i:] if t2 <= window_end)
                rate = count
                if rate > limit:
                    penalty += (rate - limit) ** 2
        return penalty

    def _retry_penalty(self, plan: PlanIR) -> float:
        penalty = 0.0
        for node in plan.nodes.values():
            failure_prob = node.func.metadata.get("failure_prob", 0.0)
            expected_retries = node.retry_policy.max_retries * failure_prob
            penalty += failure_prob * expected_retries * node.func.expected_latency_ms
        return penalty


def _conflict(a: Tuple[ResourceAccess, ...], b: Tuple[ResourceAccess, ...]) -> bool:
    for ra in a:
        for rb in b:
            if ra.resource != rb.resource:
                continue
            if ra.mode == "R" and rb.mode == "R":
                continue
            return True
    return False


class TokenBucket:
    def __init__(self, rate: float, capacity: float) -> None:
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_time = 0.0

    def _refill(self, t: float) -> None:
        if t <= self.last_time:
            return
        self.tokens = min(self.capacity, self.tokens + self.rate * (t - self.last_time))
        self.last_time = t

    def has_token_at(self, t: float) -> bool:
        self._refill(t)
        return self.tokens >= 1.0

    def consume(self, t: float) -> bool:
        self._refill(t)
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    def consume_at(self, t: float) -> bool:
        return self.consume(t)

