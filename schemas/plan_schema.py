from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple


class PlanSchemaValidator:
    def validate(self, payload: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        nodes = payload.get("nodes")
        edges = payload.get("edges")
        if not isinstance(nodes, list):
            errors.append("Missing nodes")
            return errors
        if not isinstance(edges, (list, dict)):
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
                if node_id in node_ids:
                    errors.append(f"Duplicate node id: {node_id}")
                node_ids.add(node_id)
            if "tool" not in node:
                errors.append(f"Node {node_id} missing tool")
            if "params" not in node:
                errors.append(f"Node {node_id} missing params")
            elif not isinstance(node.get("params"), dict):
                errors.append(f"Node {node_id} params must be dict")
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
                mode = str(res.get("mode", "R")).upper()
                if mode not in {"R", "W"}:
                    errors.append(f"Node {node_id} resource invalid mode")
            retry = node.get("retry")
            if retry:
                if retry.get("max", 0) < 0:
                    errors.append(f"Node {node_id} retry max invalid")
                if retry.get("gamma", 0.0) <= 0:
                    errors.append(f"Node {node_id} retry gamma invalid")
                if retry.get("jitter", 0.0) < 0:
                    errors.append(f"Node {node_id} retry jitter invalid")
            if node.get("effect", {}).get("side") != "pure":
                if not node.get("idempotency_key"):
                    errors.append(f"Node {node_id} missing idempotency_key")
                if node.get("idempotency_key") == "":
                    errors.append(f"Node {node_id} empty idempotency_key")
            if node.get("tool") == "":
                errors.append(f"Node {node_id} empty tool name")
            for ref_id in self._collect_refs(node.get("params")):
                if ref_id not in node_ids and ref_id is not None:
                    errors.append(f"Node {node_id} references missing node: {ref_id}")
        edge_entries: List[Dict[str, Any]] = []
        if isinstance(edges, list):
            edge_entries = edges
        elif isinstance(edges, dict):
            for key in ("data", "resource", "sync"):
                bucket = edges.get(key, [])
                if isinstance(bucket, list):
                    edge_entries.extend(bucket)
        seen_edges = set()
        for edge in edge_entries:
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
            key = (src, dst)
            if key in seen_edges:
                errors.append(f"Duplicate edge: {src}->{dst}")
            seen_edges.add(key)
        data_edges = []
        if isinstance(edges, list):
            data_edges = edges
        elif isinstance(edges, dict):
            for key in ("data", "resource", "sync"):
                bucket = edges.get(key, [])
                if isinstance(bucket, list):
                    data_edges.extend(bucket)
        for edge in data_edges:
            if edge.get("src") == edge.get("dst"):
                errors.append("Self edge is not allowed")
        if not self._is_acyclic(node_ids, edge_entries):
            errors.append("Cycle detected in edges")
        return errors

    def _collect_refs(self, value: Any) -> Set[Optional[str]]:
        refs: Set[Optional[str]] = set()
        if isinstance(value, dict):
            if value.get("ref"):
                ref = value["ref"]
                if isinstance(ref, (list, tuple)) and ref:
                    refs.add(str(ref[0]))
                else:
                    refs.add(None)
            for v in value.values():
                refs.update(self._collect_refs(v))
        elif isinstance(value, list):
            for v in value:
                refs.update(self._collect_refs(v))
        return refs

    def _is_acyclic(self, node_ids: Set[str], edges: List[Dict[str, Any]]) -> bool:
        incoming: Dict[str, int] = {n: 0 for n in node_ids}
        successors: Dict[str, List[str]] = {n: [] for n in node_ids}
        for edge in edges:
            src = edge.get("src")
            dst = edge.get("dst")
            if not src or not dst:
                continue
            if src not in node_ids or dst not in node_ids:
                continue
            incoming[dst] += 1
            successors[src].append(dst)
        ready = [n for n, deg in incoming.items() if deg == 0]
        seen = 0
        while ready:
            cur = ready.pop()
            seen += 1
            for succ in successors.get(cur, []):
                incoming[succ] -= 1
                if incoming[succ] == 0:
                    ready.append(succ)
        return seen == len(node_ids)

