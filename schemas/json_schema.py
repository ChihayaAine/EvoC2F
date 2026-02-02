from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str
    code: str = "invalid"

    def format(self) -> str:
        if not self.path:
            return self.message
        return f"{self.path}: {self.message}"


@dataclass
class SchemaRegistry:
    schemas: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def register(self, name: str, schema: Dict[str, Any]) -> None:
        if not name:
            raise ValueError("schema name required")
        self.schemas[name] = schema

    def get(self, name: str) -> Dict[str, Any]:
        if name not in self.schemas:
            raise KeyError(f"schema not found: {name}")
        return self.schemas[name]

    def list(self) -> List[str]:
        return sorted(self.schemas.keys())


class SchemaValidator:
    def __init__(self, registry: Optional[SchemaRegistry] = None) -> None:
        self.registry = registry or SchemaRegistry()

    def validate(self, schema: Dict[str, Any], payload: Dict[str, Any]) -> List[str]:
        return [issue.format() for issue in self.validate_detailed(schema, payload)]

    def validate_detailed(
        self, schema: Dict[str, Any], payload: Any, path: str = ""
    ) -> List[ValidationIssue]:
        return self._validate_schema(schema, payload, path)

    def apply_defaults(self, schema: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._apply_defaults(schema, payload)

    def _validate_schema(
        self, schema: Dict[str, Any], value: Any, path: str
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        if not schema:
            return issues
        schema = self._resolve_schema(schema)
        if "oneOf" in schema:
            matches = 0
            for idx, sub in enumerate(schema.get("oneOf", [])):
                if not self._validate_schema(sub, value, path):
                    matches += 1
            if matches != 1:
                issues.append(ValidationIssue(path, "value must match exactly one schema", "oneOf"))
            return issues
        if "anyOf" in schema:
            for sub in schema.get("anyOf", []):
                if not self._validate_schema(sub, value, path):
                    return issues
            issues.append(ValidationIssue(path, "value must match at least one schema", "anyOf"))
            return issues
        if "allOf" in schema:
            for sub in schema.get("allOf", []):
                issues.extend(self._validate_schema(sub, value, path))
            return issues
        if "not" in schema:
            if not self._validate_schema(schema.get("not", {}), value, path):
                issues.append(ValidationIssue(path, "value matches forbidden schema", "not"))
                return issues
        if value is None:
            if schema.get("nullable") or self._type_allows_null(schema.get("type")):
                return issues
            issues.append(ValidationIssue(path, "value is null but not nullable", "null"))
            return issues
        expected = schema.get("type")
        if expected and not self._match_type(expected, value):
            issues.append(ValidationIssue(path, f"expected {expected}", "type"))
            return issues
        if "const" in schema and value != schema["const"]:
            issues.append(ValidationIssue(path, "value does not match const", "const"))
        enum = schema.get("enum")
        if enum is not None and value not in enum:
            issues.append(ValidationIssue(path, "value not in enum", "enum"))
        if "if" in schema and "then" in schema:
            if not self._validate_schema(schema["if"], value, path):
                issues.extend(self._validate_schema(schema["then"], value, path))
        if "if" in schema and "else" in schema:
            if self._validate_schema(schema["if"], value, path):
                issues.extend(self._validate_schema(schema["else"], value, path))
        if self._is_type(expected, "number") or self._is_type(expected, "integer"):
            issues.extend(self._check_number(schema, value, path))
        if self._is_type(expected, "string"):
            issues.extend(self._check_string(schema, value, path))
        if self._is_type(expected, "object"):
            issues.extend(self._check_object(schema, value, path))
        if self._is_type(expected, "array"):
            issues.extend(self._check_array(schema, value, path))
        return issues

    def _check_object(
        self, schema: Dict[str, Any], value: Any, path: str
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        if not isinstance(value, dict):
            return [ValidationIssue(path, "expected object", "type")]
        required = schema.get("required", [])
        for field in required:
            if field not in value:
                issues.append(ValidationIssue(f"{path}{field}", "missing field", "required"))
        props = schema.get("properties", {})
        for key, spec in props.items():
            if key in value:
                issues.extend(self._validate_schema(spec, value[key], f"{path}{key}."))
        pattern_props = schema.get("patternProperties", {})
        if pattern_props:
            for key, val in value.items():
                for pattern, spec in pattern_props.items():
                    if re.search(pattern, key):
                        issues.extend(self._validate_schema(spec, val, f"{path}{key}."))
        if schema.get("additionalProperties") is False:
            extras = [k for k in value.keys() if k not in props]
            for key in extras:
                issues.append(ValidationIssue(f"{path}{key}", "additional properties not allowed", "additional"))
        elif isinstance(schema.get("additionalProperties"), dict):
            extra_schema = schema.get("additionalProperties")
            for key, val in value.items():
                if key not in props:
                    issues.extend(self._validate_schema(extra_schema, val, f"{path}{key}."))
        min_props = schema.get("minProperties")
        max_props = schema.get("maxProperties")
        if min_props is not None and len(value) < min_props:
            issues.append(ValidationIssue(path, f"minProperties {min_props} violated", "minProperties"))
        if max_props is not None and len(value) > max_props:
            issues.append(ValidationIssue(path, f"maxProperties {max_props} violated", "maxProperties"))
        dependent = schema.get("dependentRequired", {})
        for key, deps in dependent.items():
            if key in value:
                for dep in deps:
                    if dep not in value:
                        issues.append(ValidationIssue(f"{path}{dep}", f"dependent on {key}", "dependentRequired"))
        return issues

    def _check_array(
        self, schema: Dict[str, Any], value: Any, path: str
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        if not isinstance(value, list):
            return [ValidationIssue(path, "expected array", "type")]
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if min_items is not None and len(value) < min_items:
            issues.append(ValidationIssue(path, f"minItems {min_items} violated", "minItems"))
        if max_items is not None and len(value) > max_items:
            issues.append(ValidationIssue(path, f"maxItems {max_items} violated", "maxItems"))
        if schema.get("uniqueItems"):
            seen = set()
            for item in value:
                marker = repr(item)
                if marker in seen:
                    issues.append(ValidationIssue(path, "uniqueItems violated", "uniqueItems"))
                    break
                seen.add(marker)
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                issues.extend(self._validate_schema(item_schema, item, f"{path}[{idx}]."))
        elif isinstance(item_schema, list):
            for idx, item in enumerate(value):
                if idx < len(item_schema):
                    issues.extend(self._validate_schema(item_schema[idx], item, f"{path}[{idx}]."))
        return issues

    def _match_type(self, expected: Any, value: Any) -> bool:
        mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "object": dict,
            "array": list,
            "null": type(None),
        }
        if isinstance(expected, (list, tuple)):
            return any(self._match_type(item, value) for item in expected)
        py_type = mapping.get(expected)
        if py_type is None:
            return True
        return isinstance(value, py_type)

    def _check_number(
        self, spec: Dict[str, Any], value: Any, path: str
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        if not isinstance(value, (int, float)):
            return issues
        minimum = spec.get("minimum")
        maximum = spec.get("maximum")
        exclusive_min = spec.get("exclusiveMinimum")
        exclusive_max = spec.get("exclusiveMaximum")
        multiple = spec.get("multipleOf")
        if minimum is not None and value < minimum:
            issues.append(ValidationIssue(path, f"below minimum {minimum}", "minimum"))
        if maximum is not None and value > maximum:
            issues.append(ValidationIssue(path, f"above maximum {maximum}", "maximum"))
        if exclusive_min is not None and value <= exclusive_min:
            issues.append(ValidationIssue(path, f"<= exclusiveMinimum {exclusive_min}", "exclusiveMinimum"))
        if exclusive_max is not None and value >= exclusive_max:
            issues.append(ValidationIssue(path, f">= exclusiveMaximum {exclusive_max}", "exclusiveMaximum"))
        if multiple is not None and multiple != 0 and (value / multiple) % 1 != 0:
            issues.append(ValidationIssue(path, f"not a multiple of {multiple}", "multipleOf"))
        return issues

    def _check_string(
        self, spec: Dict[str, Any], value: Any, path: str
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        if not isinstance(value, str):
            return issues
        min_len = spec.get("minLength")
        max_len = spec.get("maxLength")
        pattern = spec.get("pattern")
        fmt = spec.get("format")
        if min_len is not None and len(value) < min_len:
            issues.append(ValidationIssue(path, f"length below {min_len}", "minLength"))
        if max_len is not None and len(value) > max_len:
            issues.append(ValidationIssue(path, f"length above {max_len}", "maxLength"))
        if pattern and not re.search(pattern, value):
            issues.append(ValidationIssue(path, "pattern mismatch", "pattern"))
        if fmt and not self._match_format(fmt, value):
            issues.append(ValidationIssue(path, f"format {fmt} mismatch", "format"))
        return issues

    def _match_format(self, fmt: str, value: str) -> bool:
        if fmt == "email":
            return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", value))
        if fmt == "uri":
            parsed = urlparse(value)
            return bool(parsed.scheme and parsed.netloc)
        if fmt == "date-time":
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                return True
            except ValueError:
                return False
        return True

    def _type_allows_null(self, expected: Any) -> bool:
        if expected is None:
            return False
        if expected == "null":
            return True
        if isinstance(expected, (list, tuple)):
            return "null" in expected
        return False

    def _is_type(self, expected: Any, candidate: str) -> bool:
        if expected is None:
            return False
        if expected == candidate:
            return True
        if isinstance(expected, (list, tuple)):
            return candidate in expected
        return False

    def _apply_defaults(self, schema: Dict[str, Any], value: Any) -> Any:
        if not schema:
            return value
        schema = self._resolve_schema(schema)
        if value is None:
            if "default" in schema:
                return schema["default"]
            return value
        expected = schema.get("type")
        if self._is_type(expected, "object") and isinstance(value, dict):
            output = dict(value)
            props = schema.get("properties", {})
            for key, spec in props.items():
                if key in output:
                    output[key] = self._apply_defaults(spec, output[key])
                elif "default" in spec:
                    output[key] = spec["default"]
            return output
        if self._is_type(expected, "array") and isinstance(value, list):
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                return [self._apply_defaults(item_schema, item) for item in value]
            return value
        return value

    def _resolve_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        ref = schema.get("$ref")
        if not ref:
            return schema
        resolved = self._resolve_ref(ref, schema)
        merged = dict(resolved)
        for key, value in schema.items():
            if key != "$ref":
                merged[key] = value
        return merged

    def _resolve_ref(self, ref: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        if ref.startswith("#/"):
            return self._resolve_local_ref(ref, schema)
        return self.registry.get(ref)

    def _resolve_local_ref(self, ref: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        parts = ref.lstrip("#/").split("/")
        cursor: Any = schema
        for part in parts:
            if not isinstance(cursor, dict) or part not in cursor:
                raise KeyError(f"invalid ref: {ref}")
            cursor = cursor[part]
        if not isinstance(cursor, dict):
            raise KeyError(f"ref must resolve to object: {ref}")
        return cursor

