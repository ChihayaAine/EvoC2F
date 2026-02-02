from __future__ import annotations

from typing import Any, Dict, List


class PlanSchemaValidator:
    def validate(self, payload: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        nodes = payload.get("nodes")
        edges = payload.get("edges")
        if not isinstance(nodes, list):
            errors.append("Missing nodes")
            return errors
        if not isinstance(edges, list):
            errors.append("Missing edges")
            return errors
        node_ids = set()
        for node in nodes:
            if not isinstance(node, dict):
                errors.append("Invalid node entry")
                continue
            node_id = node.get("id")
            if not node_id:
                errors.append("Node missing id")
            else:
                node_ids.add(node_id)
            if "tool" not in node:
                errors.append(f"Node {node_id} missing tool")
            if "params" not in node:
                errors.append(f"Node {node_id} missing params")
        for edge in edges:
            if not isinstance(edge, dict):
                errors.append("Invalid edge entry")
                continue
            src = edge.get("src")
            dst = edge.get("dst")
            if not src or not dst:
                errors.append("Edge missing src/dst")
                continue
            if src not in node_ids or dst not in node_ids:
                errors.append(f"Edge references missing node: {src}->{dst}")
        return errors

