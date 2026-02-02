from __future__ import annotations

import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from ..core.compiler import CompiledPlan, ScheduledNode, TokenBucket
from ..core.plan_ir import PlanIR, PlanNode, ResourceAccess, RetryPolicy, ToolRegistry


@dataclass
class ExecutionConfig:
    concurrency_limit: int
    lock_timeout_s: float = 2.0
    backoff_base_s: float = 0.1
    max_backoff_s: float = 2.0
    jitter: float = 0.0
    circuit_breaker_window: int = 10
    circuit_breaker_threshold: float = 0.5


@dataclass
class ExecutionResult:
    outputs: Dict[str, Any]
    failures: Dict[str, Exception]
    duration_ms: float
    traces: List[Dict[str, Any]]


class CircuitBreaker:
    def __init__(self, window: int, threshold: float) -> None:
        self.window = window
        self.threshold = threshold
        self.history: List[bool] = []
        self.open = False

    def record(self, success: bool) -> None:
        self.history.append(success)
        if len(self.history) > self.window:
            self.history.pop(0)
        if len(self.history) == self.window:
            failure_rate = 1.0 - (sum(self.history) / self.window)
            self.open = failure_rate >= self.threshold

    def allow(self) -> bool:
        return not self.open


class RWLock:
    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._readers = 0
        self._writer = False

    def acquire_read(self, timeout: float) -> bool:
        end = time.time() + timeout
        with self._cond:
            while self._writer:
                remaining = end - time.time()
                if remaining <= 0:
                    return False
                self._cond.wait(timeout=remaining)
            self._readers += 1
            return True

    def acquire_write(self, timeout: float) -> bool:
        end = time.time() + timeout
        with self._cond:
            while self._writer or self._readers > 0:
                remaining = end - time.time()
                if remaining <= 0:
                    return False
                self._cond.wait(timeout=remaining)
            self._writer = True
            return True

    def release_read(self) -> None:
        with self._cond:
            self._readers = max(0, self._readers - 1)
            if self._readers == 0:
                self._cond.notify_all()

    def release_write(self) -> None:
        with self._cond:
            self._writer = False
            self._cond.notify_all()


class Executor:
    def __init__(
        self,
        registry: ToolRegistry,
        rate_limits: Optional[Dict[str, float]] = None,
        rate_bursts: Optional[Dict[str, float]] = None,
        config: Optional[ExecutionConfig] = None,
    ) -> None:
        self.registry = registry
        self.config = config or ExecutionConfig(concurrency_limit=4)
        self.rate_limits = rate_limits or {}
        self.rate_bursts = rate_bursts or {}
        self._resource_locks: Dict[str, RWLock] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._token_buckets: Dict[str, TokenBucket] = {}

    def execute(self, compiled: CompiledPlan) -> ExecutionResult:
        plan = compiled.plan
        outputs: Dict[str, Any] = {}
        failures: Dict[str, Exception] = {}
        traces: List[Dict[str, Any]] = []
        start_time = time.time()
        self._init_token_buckets(plan)
        executed: List[str] = []
        pending = set(plan.nodes.keys())
        completed: Set[str] = set()
        ready: Set[str] = {n for n in pending if not plan.predecessors(n)}
        in_flight: Dict[Future, str] = {}
        failure_event = threading.Event()

        def submit_node(node_id: str) -> None:
            node = plan.nodes[node_id]
            in_flight[executor.submit(self._execute_node, node, outputs)] = node_id

        with ThreadPoolExecutor(max_workers=self.config.concurrency_limit) as executor:
            while (pending or in_flight) and not failure_event.is_set():
                while ready and len(in_flight) < self.config.concurrency_limit:
                    node_id = self._select_ready_node(ready, compiled)
                    if not self._is_schedule_ready(node_id, compiled, start_time):
                        break
                    pending.discard(node_id)
                    ready.discard(node_id)
                    submit_node(node_id)
                if not in_flight:
                    time.sleep(0.01)
                    continue
                done, _ = wait(in_flight.keys(), timeout=0.05, return_when=FIRST_COMPLETED)
                for future in done:
                    node_id = in_flight.pop(future)
                    try:
                        out = future.result()
                        outputs[node_id] = out
                        executed.append(node_id)
                        completed.add(node_id)
                        traces.append(
                            {
                                "node_id": node_id,
                                "tool": plan.nodes[node_id].func.name,
                                "success": True,
                                "output": out,
                                "resources": [ra.resource for ra in plan.nodes[node_id].resources],
                            }
                        )
                        for succ in plan.successors(node_id):
                            if succ in pending and all(p in completed for p in plan.predecessors(succ)):
                                ready.add(succ)
                    except Exception as exc:
                        failures[node_id] = exc
                        traces.append(
                            {
                                "node_id": node_id,
                                "tool": plan.nodes[node_id].func.name,
                                "success": False,
                                "error": str(exc),
                            }
                        )
                        failure_event.set()
                        break
            if failure_event.is_set():
                self._compensate(plan, executed, outputs, traces)
        duration_ms = (time.time() - start_time) * 1000
        return ExecutionResult(
            outputs=outputs, failures=failures, duration_ms=duration_ms, traces=traces
        )

    def _execute_node(self, node: PlanNode, outputs: Dict[str, Any]) -> Any:
        breaker = self._circuit_breakers.setdefault(
            node.func.name,
            CircuitBreaker(
                window=self.config.circuit_breaker_window,
                threshold=self.config.circuit_breaker_threshold,
            ),
        )
        if not breaker.allow():
            raise RuntimeError(f"Circuit open for {node.func.name}")
        params = self._resolve_params(node.params, outputs)
        if node.idempotency_key and "__idempotency_key" not in params:
            params["__idempotency_key"] = node.idempotency_key
        attempt = 0
        while True:
            try:
                self._acquire_locks(node.resources)
                self._consume_tokens(node.resources)
                result = node.func.signature(**params)
                self._detect_undeclared_access(node, result)
                breaker.record(True)
                return result
            except Exception as exc:
                breaker.record(False)
                if attempt >= node.retry_policy.max_retries:
                    if node.retry_policy.fallback:
                        return node.retry_policy.fallback(exc)
                    raise
                if not isinstance(exc, node.retry_policy.retry_exceptions or (Exception,)):
                    raise
                attempt += 1
                time.sleep(self._backoff(attempt, node.retry_policy.backoff_gamma))
            finally:
                self._release_locks(node.resources)

    def _resolve_params(self, params: Dict[str, Any], outputs: Dict[str, Any]) -> Dict[str, Any]:
        resolved = {}
        for key, value in params.items():
            if isinstance(value, dict) and value.get("ref"):
                node_id, field = value["ref"]
                data = outputs[node_id]
                resolved[key] = data[field] if field else data
            else:
                resolved[key] = value
        return resolved

    def _resource_lock(self, resource: str) -> RWLock:
        if resource not in self._resource_locks:
            self._resource_locks[resource] = RWLock()
        return self._resource_locks[resource]

    def _acquire_locks(self, resources: Tuple[ResourceAccess, ...]) -> None:
        ordered = sorted(resources, key=lambda r: r.resource)
        acquired: List[Tuple[RWLock, str]] = []
        timeout = self.config.lock_timeout_s
        for access in ordered:
            lock = self._resource_lock(access.resource)
            ok = (
                lock.acquire_read(timeout=timeout)
                if access.is_read()
                else lock.acquire_write(timeout=timeout)
            )
            if not ok:
                for held, mode in acquired:
                    if mode == "R":
                        held.release_read()
                    else:
                        held.release_write()
                raise TimeoutError(f"Lock timeout on resource {access.resource}")
            acquired.append((lock, access.mode))

    def _release_locks(self, resources: Tuple[ResourceAccess, ...]) -> None:
        for access in sorted(resources, key=lambda r: r.resource):
            lock = self._resource_lock(access.resource)
            if access.is_read():
                lock.release_read()
            else:
                lock.release_write()

    def _init_token_buckets(self, plan: PlanIR) -> None:
        for node in plan.nodes.values():
            for access in node.resources:
                if access.resource in self.rate_limits:
                    rate = self.rate_limits[access.resource]
                    burst = self.rate_bursts.get(access.resource, rate)
                    self._token_buckets[access.resource] = TokenBucket(rate, burst)

    def _consume_tokens(self, resources: Tuple[ResourceAccess, ...]) -> None:
        now = time.time()
        for access in resources:
            bucket = self._token_buckets.get(access.resource)
            if bucket and not bucket.consume(now):
                raise RuntimeError(f"Rate limit exceeded for {access.resource}")

    def _backoff(self, attempt: int, gamma: float) -> float:
        delay = self.config.backoff_base_s * (gamma ** (attempt - 1))
        delay = min(self.config.max_backoff_s, delay)
        if self.config.jitter:
            delay *= 1.0 + (self.config.jitter * (2 * (time.time() % 1) - 1))
        return max(0.0, delay)

    def _detect_undeclared_access(self, node: PlanNode, result: Any) -> None:
        if not isinstance(result, dict):
            return
        accessed = result.get("_accessed_resources")
        if not accessed:
            return
        resources = tuple(
            ResourceAccess(resource=r["resource"], mode=r["mode"]) for r in accessed
        )
        self.registry.expand_from_trace(node.func.name, resources)

    def _select_ready_node(self, ready: Iterable[str], compiled: CompiledPlan) -> str:
        schedule = compiled.schedule
        if schedule:
            return min(ready, key=lambda n: schedule.get(n, ScheduledNode(n, 0.0, 0.0)).start_ms)
        return sorted(ready)[0]

    def _is_schedule_ready(self, node_id: str, compiled: CompiledPlan, start_time: float) -> bool:
        scheduled = compiled.schedule.get(node_id)
        if not scheduled:
            return True
        now = time.time()
        return now >= start_time + (scheduled.start_ms / 1000.0)

    def _compensate(
        self,
        plan: PlanIR,
        executed: List[str],
        outputs: Dict[str, Any],
        traces: List[Dict[str, Any]],
    ) -> None:
        for node_id in reversed(executed):
            node = plan.nodes[node_id]
            if not node.compensation:
                continue
            try:
                node.compensation(outputs.get(node_id))
                traces.append(
                    {
                        "node_id": node_id,
                        "tool": node.func.name,
                        "compensated": True,
                    }
                )
            except Exception as exc:
                traces.append(
                    {
                        "node_id": node_id,
                        "tool": node.func.name,
                        "compensated": False,
                        "error": str(exc),
                    }
                )

