from __future__ import annotations

from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from ..core.plan_ir import EffectType, Environment, ResourceAccess, SideEffect, Tool
from ..schemas.json_schema import SchemaValidator


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
            },
        )

    def _invoke(self, **kwargs: Any) -> Any:
        self.wrapper.validate_state()
        self.wrapper.validate_input(kwargs)
        output = self._call_with_timeout(kwargs)
        self.wrapper.validate_output(output)
        if isinstance(output, ToolResult):
            return {
                "output": output.output,
                "_accessed_resources": output.accessed_resources,
                "_metadata": output.metadata,
            }
        return output

    def _call_with_timeout(self, kwargs: Dict[str, Any]) -> Any:
        if not self.spec.timeout_ms:
            return self.wrapper(**kwargs)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.wrapper, **kwargs)
            try:
                return future.result(timeout=self.spec.timeout_ms / 1000.0)
            except FutureTimeout as exc:
                raise TimeoutError(f"Tool {self.spec.name} timed out") from exc


class ToolCatalog:
    def __init__(self) -> None:
        self._specs: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._specs[spec.name] = spec

    def search(self, tag: str) -> List[ToolSpec]:
        return [spec for spec in self._specs.values() if tag in spec.tags]

    def list_active(self) -> List[ToolSpec]:
        return [spec for spec in self._specs.values() if not spec.deprecated]

    def list(self) -> List[ToolSpec]:
        return list(self._specs.values())

    def get(self, name: str) -> ToolSpec:
        return self._specs[name]

