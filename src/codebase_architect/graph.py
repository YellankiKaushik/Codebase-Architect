from __future__ import annotations

from collections import defaultdict, deque
from typing import Iterable
from .models import Edge, Node, SCHEMA_VERSION

class CodeGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}
        self.outgoing: dict[str, set[str]] = defaultdict(set)
        self.incoming: dict[str, set[str]] = defaultdict(set)

    def add_node(self, node: Node) -> None:
        current = self.nodes.get(node.id)
        if current is None:
            self.nodes[node.id] = node
            return
        seen = {e.id for e in current.evidence}
        current.evidence.extend(e for e in node.evidence if e.id not in seen)
        current.properties.update({k: v for k, v in node.properties.items() if k not in current.properties})
        if current.path is None and node.path is not None:
            current.path = node.path

    def add_edge(self, edge: Edge) -> None:
        current = self.edges.get(edge.id)
        if current is None:
            self.edges[edge.id] = edge
            self.outgoing[edge.source].add(edge.id)
            self.incoming[edge.target].add(edge.id)
            return
        seen = {e.id for e in current.evidence}
        current.evidence.extend(e for e in edge.evidence if e.id not in seen)
        current.confidence = max(current.confidence, edge.confidence)

    def add_many(self, nodes: Iterable[Node], edges: Iterable[Edge]) -> None:
        for node in nodes: self.add_node(node)
        for edge in edges: self.add_edge(edge)

    def nodes_by_kind(self, kind: str) -> list[Node]:
        return sorted((n for n in self.nodes.values() if n.kind == kind), key=lambda n: (n.path or "", n.name))

    def edges_by_kind(self, kind: str) -> list[Edge]:
        return [e for e in self.edges.values() if e.kind == kind]

    def neighbors(self, node_id: str, depth: int = 1) -> set[str]:
        seen = {node_id}
        frontier = deque([(node_id, 0)])
        while frontier:
            current, level = frontier.popleft()
            if level >= depth: continue
            for edge_id in self.outgoing.get(current, set()) | self.incoming.get(current, set()):
                edge = self.edges[edge_id]
                other = edge.target if edge.source == current else edge.source
                if other not in seen:
                    seen.add(other); frontier.append((other, level + 1))
        return seen

    def to_dict(self) -> dict:
        return {"schema_version": SCHEMA_VERSION, "nodes": [n.to_dict() for n in sorted(self.nodes.values(), key=lambda n: n.id)], "edges": [e.to_dict() for e in sorted(self.edges.values(), key=lambda e: e.id)]}

    @classmethod
    def from_dict(cls, raw: dict) -> "CodeGraph":
        graph = cls()
        for node_raw in raw.get("nodes", []): graph.add_node(Node.from_dict(node_raw))
        for edge_raw in raw.get("edges", []): graph.add_edge(Edge.from_dict(edge_raw))
        return graph
