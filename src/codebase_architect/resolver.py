from __future__ import annotations

import json
import posixpath
from pathlib import Path

from .analyzers.base import evidence, stable_id
from .graph import CodeGraph
from .models import Classification, Edge, Node


EXTENSIONS = ("", ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", "/__init__.py", "/index.py", "/index.js", "/index.ts", "/index.tsx")


def resolve_graph(repository: Path, graph: CodeGraph) -> dict:
    stats = {"edges_added": 0, "imports_resolved": 0, "calls_resolved": 0, "warnings": []}
    file_by_path = {node.path: node for node in graph.nodes_by_kind("FILE") if node.path}
    ast_paths = {path for path, node in file_by_path.items() if node.properties.get("capability") == "AST"}
    symbols_by_path = _symbols_by_path(graph)
    exports_by_path = _exports_by_path(graph)
    import_targets_by_file: dict[str, set[str]] = {path: set() for path in file_by_path}

    for edge in list(graph.edges.values()):
        if edge.kind != "IMPORTS":
            continue
        source = graph.nodes.get(edge.source)
        module = graph.nodes.get(edge.target)
        if not source or not module or source.kind != "FILE" or module.kind != "MODULE" or not source.path:
            continue
        target_path = _resolve_module(repository, source.path, module.name, file_by_path)
        if not target_path:
            module.properties["resolution"] = "UNKNOWN"
            continue
        target_file = file_by_path[target_path]
        module.properties["resolution"] = target_path
        module.properties["external"] = False
        import_targets_by_file[source.path].add(target_path)
        ev = edge.evidence[:1] or source.evidence[:1]
        added = _add_edge(graph, "IMPORTS", source.id, target_file.id, ev, classification=Classification.VERIFIED.value, confidence=1.0, properties={"resolved_from": module.name})
        added += _add_edge(graph, "RESOLVES_TO", module.id, target_file.id, ev, classification=Classification.VERIFIED.value, confidence=1.0, properties={"module": module.name})
        stats["edges_added"] += added
        if added:
            stats["imports_resolved"] += 1

    for edge in list(graph.edges.values()):
        if edge.kind != "CALLS":
            continue
        source = graph.nodes.get(edge.source)
        target = graph.nodes.get(edge.target)
        if not source or not target or not target.properties.get("unresolved"):
            continue
        candidates = _call_candidates(source, target.name, symbols_by_path, exports_by_path, import_targets_by_file)
        if not candidates:
            continue
        resolved = candidates[0]
        ev = edge.evidence[:1] or source.evidence[:1]
        verified_by_ast = bool(source.path in ast_paths and (resolved.path == source.path or resolved.path in import_targets_by_file.get(source.path, set())))
        added = _add_edge(
            graph, "CALLS", source.id, resolved.id, ev,
            classification=Classification.VERIFIED.value if verified_by_ast else Classification.INFERRED.value,
            confidence=0.94 if verified_by_ast else 0.78,
            properties={"resolved_from": target.name, "resolver": "repository-symbol-resolver"},
        )
        stats["edges_added"] += added
        if added:
            stats["calls_resolved"] += 1

    for edge in list(graph.edges.values()):
        if edge.kind == "EXPOSES":
            handler = graph.nodes.get(edge.source)
            endpoint = graph.nodes.get(edge.target)
            if handler and endpoint and endpoint.kind == "API_ENDPOINT":
                stats["edges_added"] += _add_edge(graph, "HANDLES", endpoint.id, handler.id, edge.evidence[:1], classification=Classification.VERIFIED.value, confidence=1.0)

    for endpoint in graph.nodes_by_kind("API_ENDPOINT"):
        if not endpoint.path:
            continue
        handler_name = endpoint.properties.get("handler")
        if not handler_name:
            continue
        searched_paths = [endpoint.path, *sorted(import_targets_by_file.get(endpoint.path, set()))]
        for symbol in [item for path in searched_paths for item in symbols_by_path.get(path, [])]:
            if symbol.name == handler_name or symbol.properties.get("qualified_name") == handler_name or str(symbol.properties.get("qualified_name", "")).endswith("." + handler_name.split(".")[-1]):
                stats["edges_added"] += _add_edge(graph, "HANDLES", endpoint.id, symbol.id, endpoint.evidence[:1], classification=Classification.INFERRED.value, confidence=0.72, properties={"handler": handler_name})
                break

    return stats


def _symbols_by_path(graph: CodeGraph) -> dict[str, list[Node]]:
    result: dict[str, list[Node]] = {}
    for node in graph.nodes.values():
        if node.kind in {"FUNCTION", "METHOD", "CLASS"} and node.path:
            result.setdefault(node.path, []).append(node)
    return result


def _exports_by_path(graph: CodeGraph) -> dict[str, list[Node]]:
    result: dict[str, list[Node]] = {}
    for path, nodes in _symbols_by_path(graph).items():
        result[path] = [node for node in nodes if node.properties.get("exported", True)]
    return result


def _resolve_module(repository: Path, source_path: str, module: str, file_by_path: dict[str | None, Node]) -> str | None:
    normalized = module.replace("\\", "/")
    if normalized.startswith("."):
        base = Path(source_path).parent
        root = (base / normalized).as_posix()
        for suffix in EXTENSIONS:
            candidate = posixpath.normpath(root + suffix).replace("//", "/")
            if candidate in file_by_path:
                return candidate
        return None
    dotted = normalized.replace(".", "/")
    for suffix in EXTENSIONS:
        candidate = posixpath.normpath(dotted + suffix).replace("//", "/")
        if candidate in file_by_path:
            return candidate
    tsconfig = _load_tsconfig_paths(repository)
    for prefix, targets in tsconfig.items():
        if normalized == prefix or normalized.startswith(prefix.rstrip("*")):
            tail = normalized[len(prefix.rstrip("*")):]
            for target in targets:
                mapped = target.replace("*", tail).strip("/")
                for suffix in EXTENSIONS:
                    candidate = posixpath.normpath(mapped + suffix).replace("//", "/")
                    if candidate in file_by_path:
                        return candidate
    return None


def _load_tsconfig_paths(repository: Path) -> dict[str, list[str]]:
    path = repository / "tsconfig.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    options = raw.get("compilerOptions", {}) if isinstance(raw, dict) else {}
    base = str(options.get("baseUrl", "")).strip("./")
    result: dict[str, list[str]] = {}
    for key, values in (options.get("paths", {}) or {}).items():
        if isinstance(values, list):
            result[key] = ["/".join(part for part in (base, str(value)) if part) for value in values]
    return result


def _call_candidates(source: Node, call_name: str, symbols_by_path: dict[str, list[Node]], exports_by_path: dict[str, list[Node]], import_targets_by_file: dict[str, set[str]]) -> list[Node]:
    if not source.path:
        return []
    simple = call_name.split(".")[-1]
    local = [node for node in symbols_by_path.get(source.path, []) if node.id != source.id and (node.name == simple or node.properties.get("qualified_name") == call_name)]
    if local:
        return local
    imported: list[Node] = []
    for target_path in sorted(import_targets_by_file.get(source.path, set())):
        for node in exports_by_path.get(target_path, []):
            qname = str(node.properties.get("qualified_name", node.name))
            if qname == call_name or qname.endswith("." + simple):
                imported.insert(0, node)
            elif node.name == simple or node.name == call_name.split(".")[0]:
                imported.append(node)
    if imported:
        return imported
    # Last resort for common controller->service->repository style calls.
    lower_call = call_name.lower()
    for target_path in sorted(import_targets_by_file.get(source.path, set())):
        for node in exports_by_path.get(target_path, []):
            if node.kind in {"METHOD", "FUNCTION"} and (node.name.lower() in lower_call or lower_call.endswith(node.name.lower())):
                imported.append(node)
    return imported


def _add_edge(graph: CodeGraph, kind: str, source: str, target: str, ev, *, classification: str, confidence: float, properties: dict | None = None) -> int:
    edge = Edge(
        id=f"EDGE-{stable_id(kind, source, target, str(properties or {}))}",
        kind=kind, source=source, target=target,
        properties=properties or {},
        classification=classification, confidence=confidence, evidence=list(ev),
    )
    before = len(graph.edges)
    graph.add_edge(edge)
    return 1 if len(graph.edges) > before else 0
