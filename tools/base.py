from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from core.plan_ir import EffectType, Environment, ResourceAccess, SideEffect, Tool
from schemas.json_schema import SchemaValidator


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    resources: List[Dict[str, str]] = field(default_factory=list)
    effect: str = "read"
    environment: str = "external"
    version: str = "v1"
    tags: List[str] = field(default_factory=list)
    owner: str = "system"
    timeout_ms: int = 0
    deprecated: bool = False
    rate_limit_per_sec: Optional[float] = None
    idempotency_required: bool = False
    retry_max: int = 0
    retry_backoff_gamma: float = 2.0

    def validate(self) -> None:
        if not self.name:
            raise ValueError("ToolSpec name required")
        if not isinstance(self.input_schema, dict) or not isinstance(self.output_schema, dict):
            raise ValueError("ToolSpec schemas must be dict")
        if self.effect not in {"pure", "read", "write"}:
            raise ValueError("ToolSpec effect must be pure/read/write")
        if self.environment not in {"local", "external"}:
            raise ValueError("ToolSpec environment must be local/external")
        for res in self.resources:
            if "resource" not in res:
                raise ValueError("Resource entry missing resource name")
            mode = res.get("mode", "R").upper()
            if mode not in {"R", "W"}:
                raise ValueError("Resource entry mode must be R or W")
        if self.timeout_ms < 0:
            raise ValueError("ToolSpec timeout must be non-negative")
        if self.retry_max < 0:
            raise ValueError("ToolSpec retry_max must be non-negative")
        if self.retry_backoff_gamma <= 0:
            raise ValueError("ToolSpec retry_backoff_gamma must be positive")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "resources": list(self.resources),
            "effect": self.effect,
            "environment": self.environment,
            "version": self.version,
            "tags": list(self.tags),
            "owner": self.owner,
            "timeout_ms": self.timeout_ms,
            "deprecated": self.deprecated,
            "rate_limit_per_sec": self.rate_limit_per_sec,
            "idempotency_required": self.idempotency_required,
            "retry_max": self.retry_max,
            "retry_backoff_gamma": self.retry_backoff_gamma,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ToolSpec":
        return cls(
            name=payload["name"],
            description=payload.get("description", ""),
            input_schema=payload.get("input_schema", {}),
            output_schema=payload.get("output_schema", {}),
            resources=payload.get("resources", []),
            effect=payload.get("effect", "read"),
            environment=payload.get("environment", "external"),
            version=payload.get("version", "v1"),
            tags=payload.get("tags", []),
            owner=payload.get("owner", "system"),
            timeout_ms=int(payload.get("timeout_ms", 0)),
            deprecated=bool(payload.get("deprecated", False)),
            rate_limit_per_sec=payload.get("rate_limit_per_sec"),
            idempotency_required=bool(payload.get("idempotency_required", False)),
            retry_max=int(payload.get("retry_max", 0)),
            retry_backoff_gamma=float(payload.get("retry_backoff_gamma", 2.0)),
        )


@dataclass
class ToolResult:
    output: Any
    accessed_resources: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolWrapper:
    def __init__(self, spec: ToolSpec, handler: Callable[..., Any]) -> None:
        self.spec = spec
        self.handler = handler
        self.validator = SchemaValidator()

    def __call__(self, **kwargs: Any) -> Any:
        return self.handler(**kwargs)

    def prepare_input(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_state()
        payload = self.validator.apply_defaults(self.spec.input_schema, payload)
        self.validate_input(payload)
        return payload

    def validate_input(self, payload: Dict[str, Any]) -> None:
        errors = self.validator.validate(self.spec.input_schema, payload)
        if errors:
            raise ValueError("; ".join(errors))

    def validate_output(self, output: Any) -> None:
        if output is None and self.spec.output_schema.get("nullable") is False:
            raise ValueError("Output cannot be null")
        if isinstance(output, dict):
            errors = self.validator.validate(self.spec.output_schema, output)
            if errors:
                raise ValueError("; ".join(errors))

    def validate_state(self) -> None:
        if self.spec.deprecated:
            raise RuntimeError(f"Tool {self.spec.name} is deprecated")


def to_effect(effect: str, environment: str) -> EffectType:
    side = {
        "pure": SideEffect.PURE,
        "read": SideEffect.READ,
        "write": SideEffect.WRITE,
    }.get(effect, SideEffect.WRITE)
    env = Environment.EXTERNAL if environment == "external" else Environment.LOCAL
    return EffectType(side_effect=side, environment=env)


def to_resources(resources: Sequence[Dict[str, str]]) -> Tuple[ResourceAccess, ...]:
    converted: List[ResourceAccess] = []
    for res in resources:
        mode = res.get("mode", "R").upper()
        converted.append(ResourceAccess(resource=res["resource"], mode=mode))
    return tuple(converted)


class ToolAdapter:
    def __init__(self, spec: ToolSpec, handler: Callable[..., Any]) -> None:
        self.spec = spec
        self.wrapper = ToolWrapper(spec, handler)
        self.spec.validate()
        self.stats = ToolStats()

    def as_core_tool(self, latency_ms: float, cost: float) -> Tool:
        return Tool(
            name=self.spec.name,
            signature=self._invoke,
            effect=to_effect(self.spec.effect, self.spec.environment),
            resources=to_resources(self.spec.resources),
            expected_latency_ms=latency_ms,
            expected_cost=cost,
            metadata={
                "description": self.spec.description,
                "version": self.spec.version,
                "tags": self.spec.tags,
                "owner": self.spec.owner,
                "timeout_ms": self.spec.timeout_ms,
                "deprecated": self.spec.deprecated,
                "rate_limit_per_sec": self.spec.rate_limit_per_sec,
                "idempotency_required": self.spec.idempotency_required,
                "retry_max": self.spec.retry_max,
                "retry_backoff_gamma": self.spec.retry_backoff_gamma,
            },
        )

    def _invoke(self, **kwargs: Any) -> Any:
        kwargs = self.wrapper.prepare_input(kwargs)
        start = perf_counter()
        try:
            output = self._call_with_timeout(kwargs)
            self.wrapper.validate_output(output)
            payload = self._normalize_output(output)
            self.stats.record_success((perf_counter() - start) * 1000)
            return payload
        except Exception as exc:
            self.stats.record_failure((perf_counter() - start) * 1000, str(exc))
            raise

    def _call_with_timeout(self, kwargs: Dict[str, Any]) -> Any:
        if not self.spec.timeout_ms:
            return self.wrapper(**kwargs)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.wrapper, **kwargs)
            try:
                return future.result(timeout=self.spec.timeout_ms / 1000.0)
            except FutureTimeout as exc:
                raise TimeoutError(f"Tool {self.spec.name} timed out") from exc

    def _normalize_output(self, output: Any) -> Any:
        if isinstance(output, ToolResult):
            return {
                "output": output.output,
                "_accessed_resources": output.accessed_resources,
                "_metadata": output.metadata,
            }
        return output

    def stats_snapshot(self) -> Dict[str, Any]:
        return self.stats.as_dict()


class ToolCatalog:
    def __init__(self) -> None:
        self._specs: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        spec.validate()
        self._specs[spec.name] = spec

    def search(self, tag: str) -> List[ToolSpec]:
        return [spec for spec in self._specs.values() if tag in spec.tags]

    def search_name(self, keyword: str) -> List[ToolSpec]:
        needle = keyword.lower()
        return [spec for spec in self._specs.values() if needle in spec.name.lower()]

    def search_owner(self, owner: str) -> List[ToolSpec]:
        return [spec for spec in self._specs.values() if spec.owner == owner]

    def list_active(self) -> List[ToolSpec]:
        return [spec for spec in self._specs.values() if not spec.deprecated]

    def list(self) -> List[ToolSpec]:
        return list(self._specs.values())

    def get(self, name: str) -> ToolSpec:
        return self._specs[name]

    def remove(self, name: str) -> None:
        if name in self._specs:
            self._specs.pop(name)

    def update(self, spec: ToolSpec) -> None:
        spec.validate()
        self._specs[spec.name] = spec

    def register_many(self, specs: Iterable[ToolSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def count(self) -> int:
        return len(self._specs)

    def export(self) -> Dict[str, Any]:
        return {"tools": [spec.to_dict() for spec in self._specs.values()]}

    def load(self, payload: Dict[str, Any]) -> None:
        for spec in payload.get("tools", []):
            self.register(ToolSpec.from_dict(spec))


@dataclass
class ToolStats:
    calls: int = 0
    successes: int = 0
    failures: int = 0
    avg_latency_ms: float = 0.0
    last_error: Optional[str] = None

    def record_success(self, latency_ms: float) -> None:
        self.calls += 1
        self.successes += 1
        self._update_latency(latency_ms)

    def record_failure(self, latency_ms: float, error: str) -> None:
        self.calls += 1
        self.failures += 1
        self.last_error = error
        self._update_latency(latency_ms)

    @property
    def success_rate(self) -> float:
        if self.calls == 0:
            return 0.0
        return self.successes / self.calls

    @property
    def failure_rate(self) -> float:
        if self.calls == 0:
            return 0.0
        return self.failures / self.calls

    def as_dict(self) -> Dict[str, Any]:
        return {
            "calls": self.calls,
            "successes": self.successes,
            "failures": self.failures,
            "avg_latency_ms": self.avg_latency_ms,
            "last_error": self.last_error,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
        }

    def _update_latency(self, latency_ms: float) -> None:
        if self.calls == 1:
            self.avg_latency_ms = latency_ms
        else:
            self.avg_latency_ms = (
                self.avg_latency_ms * (self.calls - 1) + latency_ms
            ) / self.calls

