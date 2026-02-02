"""Schema validators."""

from typing import Any, Dict, List

from .json_schema import SchemaValidator
from .plan_schema import PlanSchemaValidator

def validate_plan(payload: Dict[str, Any]) -> List[str]:
    return PlanSchemaValidator().validate(payload)


__all__ = ["SchemaValidator", "PlanSchemaValidator", "validate_plan"]

