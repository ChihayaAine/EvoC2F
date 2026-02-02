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
            effect = node.get("effect")
            if effect:
                side = effect.get("side")
                env = effect.get("env")
                if side not in {"pure", "read", "write"}:
                    errors.append(f"Node {node_id} invalid effect side")
                if env not in {"local", "external"}:
                    errors.append(f"Node {node_id} invalid effect env")
            resources = node.get("resources", [])
            if not isinstance(resources, list):
                errors.append(f"Node {node_id} resources must be list")
            for res in resources:
                if not isinstance(res, dict):
                    errors.append(f"Node {node_id} invalid resource entry")
                    continue
                if "resource" not in res:
                    errors.append(f"Node {node_id} resource missing name")
                if res.get("mode") not in {"R", "W"}:
                    errors.append(f"Node {node_id} resource invalid mode")
            retry = node.get("retry")
            if retry:
                if retry.get("max", 0) < 0:
                    errors.append(f"Node {node_id} retry max invalid")
                if retry.get("gamma", 0.0) <= 0:
                    errors.append(f"Node {node_id} retry gamma invalid")
            if node.get("effect", {}).get("side") != "pure" and not node.get("idempotency_key"):
                errors.append(f"Node {node_id} missing idempotency_key")
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
        data_edges = edges if isinstance(edges, list) else []
        for edge in data_edges:
            if edge.get("src") == edge.get("dst"):
                errors.append("Self edge is not allowed")
        return errors

