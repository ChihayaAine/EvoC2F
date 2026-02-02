from __future__ import annotations

from typing import Any, Dict, List, Tuple


class SchemaValidator:
    def validate(self, schema: Dict[str, Any], payload: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        required = schema.get("required", [])
        for field in required:
            if field not in payload:
                errors.append(f"Missing field: {field}")
        errors.extend(self._validate_properties(schema, payload, path=""))
        return errors

    def apply_defaults(self, schema: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        output = dict(payload)
        props = schema.get("properties", {})
        for key, spec in props.items():
            if key not in output and "default" in spec:
                output[key] = spec["default"]
        return output

    def _validate_properties(
        self, schema: Dict[str, Any], payload: Dict[str, Any], path: str
    ) -> List[str]:
        errors: List[str] = []
        props = schema.get("properties", {})
        for key, spec in props.items():
            if key not in payload:
                continue
            value = payload[key]
            expected = spec.get("type")
            if expected and not self._match_type(expected, value):
                errors.append(f"{path}{key}: expected {expected}")
            enum = spec.get("enum")
            if enum and value not in enum:
                errors.append(f"{path}{key}: value not in enum")
            if expected == "number":
                errors.extend(self._check_number(spec, value, f"{path}{key}"))
            if expected == "string":
                errors.extend(self._check_string(spec, value, f"{path}{key}"))
            if expected == "object":
                child = self._validate_properties(spec, value, f"{path}{key}.")
                errors.extend(child)
            if expected == "array":
                item_schema = spec.get("items", {})
                for idx, item in enumerate(value):
                    if item_schema:
                        errors.extend(
                            self._validate_properties(item_schema, item, f"{path}{key}[{idx}].")
                        )
        return errors

    def _match_type(self, expected: str, value: Any) -> bool:
        mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "object": dict,
            "array": list,
        }
        py_type = mapping.get(expected)
        if py_type is None:
            return True
        return isinstance(value, py_type)

    def _check_number(self, spec: Dict[str, Any], value: Any, path: str) -> List[str]:
        errors: List[str] = []
        minimum = spec.get("minimum")
        maximum = spec.get("maximum")
        if minimum is not None and value < minimum:
            errors.append(f"{path}: below minimum {minimum}")
        if maximum is not None and value > maximum:
            errors.append(f"{path}: above maximum {maximum}")
        return errors

    def _check_string(self, spec: Dict[str, Any], value: Any, path: str) -> List[str]:
        errors: List[str] = []
        min_len = spec.get("minLength")
        max_len = spec.get("maxLength")
        if min_len is not None and len(value) < min_len:
            errors.append(f"{path}: length below {min_len}")
        if max_len is not None and len(value) > max_len:
            errors.append(f"{path}: length above {max_len}")
        return errors

