from __future__ import annotations

import hashlib
from pathlib import Path

from ..models import Edge, Evidence, FileAnalysis, Node

def stable_id(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:20]

def evidence(path: str, content_hash: str, line: int | None = None, symbol: str | None = None, note: str | None = None, analyzer: str | None = None) -> Evidence:
    return Evidence(
        id=f"EVD-{stable_id(path, str(line), symbol or '', note or '')}",
        path=path, line_start=line, line_end=line, symbol=symbol,
        content_hash=content_hash, note=note, analyzer=analyzer,
    )

def file_node(path: str, content_hash: str, language: str, *, analyzer: str = "scanner", capability: str = "STRUCTURAL", backend: str = "filesystem") -> Node:
    return Node(
        id=f"FILE-{stable_id(path)}", kind="FILE", name=Path(path).name, path=path,
        properties={"language": language, "analyzer": analyzer, "capability": capability, "backend": backend},
        evidence=[evidence(path, content_hash, 1, note="file exists", analyzer=analyzer)],
    )

def add_contains(analysis: FileAnalysis, parent_id: str, child: Node) -> None:
    analysis.edges.append(Edge(
        id=f"EDGE-{stable_id('CONTAINS', parent_id, child.id)}",
        kind="CONTAINS", source=parent_id, target=child.id, evidence=child.evidence[:1],
    ))
