from __future__ import annotations

import re
from collections.abc import Iterable

from ..models import AnalyzerCapability, Classification, Edge, FileAnalysis, Node
from .base import add_contains, evidence, file_node, stable_id

try:  # Optional JS/TS AST backend; structural fallback remains the core baseline.
    from tree_sitter import Language, Node as TSNode, Parser
    import tree_sitter_javascript
    import tree_sitter_typescript
except Exception:  # pragma: no cover - exercised by fallback tests via monkeypatch.
    Language = None
    Parser = None
    TSNode = object
    tree_sitter_javascript = None
    tree_sitter_typescript = None

IMPORT_RE = re.compile(r"""(?:import\s+(?:([^'"]+?)\s+from\s+)?|require\s*\()\s*['"]([^'"]+)['"]""")
FUNCTION_RE = re.compile(r"""(?m)^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(""")
ARROW_RE = re.compile(r"""(?m)^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>""")
CLASS_RE = re.compile(r"""(?m)^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)""")
METHOD_RE = re.compile(r"""(?m)^\s*(?:static\s+)?(?:async\s+)?([A-Za-z_$][\w$]*|constructor)\s*\([^)]*\)\s*\{""")
COMMONJS_EXPORT_RE = re.compile(r"""(?m)^\s*(?:module\.exports|exports\.([A-Za-z_$][\w$]*))\s*=""")
ROUTE_RE = re.compile(r"""\b(?:app|router|server)\.(get|post|put|patch|delete|options|head)\s*\(\s*['"`]([^'"`]+)['"`]\s*(?:,\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?))?""", re.IGNORECASE)
ENV_RE = re.compile(r"""\bprocess\.env(?:\.([A-Za-z_][A-Za-z0-9_]*)|\[['"]([A-Za-z_][A-Za-z0-9_]*)['"]\])""")
CALL_RE = re.compile(r"""\b([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*\(""")
EVENT_PUBLISH_RE = re.compile(r"""\b(?:emit|publish|send)\s*\(\s*['"`]([^'"`]+)['"`]""")
EVENT_CONSUME_RE = re.compile(r"""\b(?:on|subscribe|consume)\s*\(\s*['"`]([^'"`]+)['"`]""")
NEXT_ROUTE_EXPORT_RE = re.compile(r"""(?m)^\s*export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s*\(""")

STACK_MODULES = {
    "express": "Express", "fastify": "Fastify", "@nestjs": "NestJS",
    "next": "Next.js", "react": "React", "vue": "Vue", "svelte": "Svelte",
    "prisma": "Prisma", "@prisma": "Prisma", "typeorm": "TypeORM",
    "sequelize": "Sequelize", "mongoose": "MongoDB", "pg": "PostgreSQL",
    "mysql": "MySQL", "redis": "Redis",
}

def analyze(path: str, content_hash: str, source: str, language: str) -> FileAnalysis:
    ast = _analyze_ast(path, content_hash, source, language)
    if ast is not None:
        return ast
    return _analyze_structural(path, content_hash, source, language)

def _analyze_structural(path: str, content_hash: str, source: str, language: str) -> FileAnalysis:
    analysis = FileAnalysis(path=path, content_hash=content_hash, analyzer="javascript", capability=AnalyzerCapability.STRUCTURAL.value, backend="structural-js-ts")
    fnode = file_node(path, content_hash, language, analyzer="javascript", capability=AnalyzerCapability.STRUCTURAL.value, backend="structural-js-ts")
    analysis.nodes.append(fnode)
    for match in IMPORT_RE.finditer(source):
        clause, module, line = match.group(1) or "", match.group(2), _line(source, match.start())
        imported_names = _imported_names(clause)
        target = Node(
            id=f"MODULE-{stable_id(module)}", kind="MODULE", name=module,
            properties={"external": not module.startswith((".", "/")), "language": language, "imported_names": imported_names},
            evidence=[evidence(path, content_hash, line, note=f"import {module}", analyzer="javascript")],
        )
        analysis.nodes.append(target)
        analysis.edges.append(Edge(
            id=f"EDGE-{stable_id('IMPORTS', fnode.id, target.id, str(line))}",
            kind="IMPORTS", source=fnode.id, target=target.id,
            properties={"module": module, "imported_names": imported_names},
            evidence=target.evidence[:],
        ))
        for prefix, stack in STACK_MODULES.items():
            if module == prefix or module.startswith(prefix + "/"):
                analysis.stack.add(stack)
    symbols: list[Node] = []
    for regex, kind in ((CLASS_RE, "CLASS"), (FUNCTION_RE, "FUNCTION"), (ARROW_RE, "FUNCTION")):
        for match in regex.finditer(source):
            name, line = match.group(1), _line(source, match.start())
            item = Node(
                id=f"{kind}-{stable_id(path, name, str(line))}", kind=kind, name=name, path=path,
                properties={"qualified_name": name, "exported": _is_exported(source, match.start())},
                evidence=[evidence(path, content_hash, line, name, analyzer="javascript")],
            )
            symbols.append(item)
            analysis.nodes.append(item)
            add_contains(analysis, fnode.id, item)
    for class_node, start, end in _class_ranges(source, symbols):
        body = source[start:end]
        for match in METHOD_RE.finditer(body):
            method_name = match.group(1)
            line = _line(source, start + match.start())
            item = Node(
                id=f"METHOD-{stable_id(path, class_node.id, method_name, str(line))}",
                kind="METHOD", name=method_name, path=path,
                properties={"qualified_name": f"{class_node.name}.{method_name}", "exported": True},
                evidence=[evidence(path, content_hash, line, method_name, analyzer="javascript")],
            )
            symbols.append(item)
            analysis.nodes.append(item)
            add_contains(analysis, class_node.id, item)
            _maybe_repository_table_edge(analysis, item, class_node.name, path, content_hash, line)
    for match in COMMONJS_EXPORT_RE.finditer(source):
        name = match.group(1) or "module.exports"
        line = _line(source, match.start())
        item = Node(
            id=f"FUNCTION-{stable_id(path, 'commonjs-export', name, str(line))}", kind="FUNCTION", name=name, path=path,
            properties={"exported": True, "commonjs": True},
            evidence=[evidence(path, content_hash, line, name, "CommonJS export", analyzer="javascript")],
        )
        symbols.append(item)
        analysis.nodes.append(item)
        add_contains(analysis, fnode.id, item)
    for match in ROUTE_RE.finditer(source):
        method, route, handler, line = match.group(1).upper(), match.group(2), match.group(3), _line(source, match.start())
        endpoint = Node(
            id=f"API-{stable_id(path, method, route, str(line))}", kind="API_ENDPOINT",
            name=f"{method} {route}", path=path, properties={"method": method, "path": route, "handler": handler},
            evidence=[evidence(path, content_hash, line, note="HTTP route registration", analyzer="javascript")],
        )
        analysis.nodes.append(endpoint)
        analysis.edges.append(Edge(
            id=f"EDGE-{stable_id('EXPOSES', fnode.id, endpoint.id)}",
            kind="EXPOSES", source=fnode.id, target=endpoint.id, evidence=endpoint.evidence[:],
        ))
    if _looks_like_next_route(path):
        analysis.stack.add("Next.js")
        route_path = _next_route_path(path)
        for match in NEXT_ROUTE_EXPORT_RE.finditer(source):
            method, line = match.group(1).upper(), _line(source, match.start())
            endpoint = Node(
                id=f"API-{stable_id(path, method, route_path, str(line))}", kind="API_ENDPOINT",
                name=f"{method} {route_path}", path=path, properties={"method": method, "path": route_path, "framework": "Next.js"},
                evidence=[evidence(path, content_hash, line, method, "Next.js route handler export", analyzer="javascript")],
            )
            analysis.nodes.append(endpoint)
            analysis.edges.append(Edge(
                id=f"EDGE-{stable_id('EXPOSES', fnode.id, endpoint.id)}",
                kind="EXPOSES", source=fnode.id, target=endpoint.id, evidence=endpoint.evidence[:],
            ))
    for match in ENV_RE.finditer(source):
        key, line = match.group(1) or match.group(2), _line(source, match.start())
        item = Node(
            id=f"CONFIG-{stable_id(key)}", kind="CONFIGURATION_KEY", name=key,
            properties={"sensitive_candidate": any(x in key.upper() for x in ("SECRET", "TOKEN", "PASSWORD", "KEY"))},
            evidence=[evidence(path, content_hash, line, note="process.env reference", analyzer="javascript")],
        )
        analysis.nodes.append(item)
        analysis.edges.append(Edge(
            id=f"EDGE-{stable_id('CONFIGURED_BY', fnode.id, item.id, str(line))}",
            kind="CONFIGURED_BY", source=fnode.id, target=item.id, evidence=item.evidence[:],
        ))
    scope = symbols[0] if len(symbols) == 1 else fnode
    for match in CALL_RE.finditer(source):
        name = match.group(1)
        if name in {"if", "for", "while", "switch", "function", "catch"}:
            continue
        line = _line(source, match.start())
        target = Node(
            id=f"FUNCTION-{stable_id('unresolved', name)}", kind="FUNCTION", name=name,
            properties={"unresolved": True}, classification=Classification.INFERRED.value,
        )
        analysis.nodes.append(target)
        analysis.edges.append(Edge(
            id=f"EDGE-{stable_id('CALLS', scope.id, target.id, str(line))}",
            kind="CALLS", source=scope.id, target=target.id,
                classification=Classification.INFERRED.value, confidence=0.55,
                evidence=[evidence(path, content_hash, line, scope.name, f"syntactic call {name}", analyzer="javascript")],
        ))
    for regex, kind in ((EVENT_PUBLISH_RE, "PUBLISHES"), (EVENT_CONSUME_RE, "CONSUMES")):
        for match in regex.finditer(source):
            event_name, line = match.group(1), _line(source, match.start())
            event = Node(
                id=f"EVENT-{stable_id(event_name)}", kind="EVENT", name=event_name,
                evidence=[evidence(path, content_hash, line, note=f"{kind.lower()} event", analyzer="javascript")],
            )
            analysis.nodes.append(event)
            analysis.edges.append(Edge(
                id=f"EDGE-{stable_id(kind, fnode.id, event.id, str(line))}",
                kind=kind, source=fnode.id, target=event.id, evidence=event.evidence[:],
            ))
    return analysis

def _analyze_ast(path: str, content_hash: str, source: str, language: str) -> FileAnalysis | None:
    tree = _parse_tree(source, language)
    if tree is None or tree.root_node.has_error:
        return None
    backend = "tree-sitter-typescript" if language == "typescript" else "tree-sitter-javascript"
    analysis = FileAnalysis(path=path, content_hash=content_hash, analyzer="javascript", capability=AnalyzerCapability.AST.value, backend=backend)
    fnode = file_node(path, content_hash, language, analyzer="javascript", capability=AnalyzerCapability.AST.value, backend=backend)
    analysis.nodes.append(fnode)
    source_bytes = source.encode("utf-8")
    symbols: list[Node] = []
    scope_by_range: list[tuple[int, int, Node]] = [(0, len(source_bytes), fnode)]

    for node in _walk(tree.root_node):
        if node.type == "import_statement":
            _add_import_statement(analysis, fnode, node, source_bytes, path, content_hash, language)
        elif node.type == "call_expression":
            _add_call_import_if_static(analysis, fnode, node, source_bytes, path, content_hash, language)
        elif node.type == "export_statement":
            _add_export_statement(analysis, fnode, node, source_bytes, path, content_hash, language)

    for node in _walk(tree.root_node):
        exported = _is_within_export(node)
        if node.type == "function_declaration":
            symbol = _add_named_symbol(analysis, fnode.id, node, source_bytes, path, content_hash, "FUNCTION", exported, _is_async(node))
            if symbol:
                symbols.append(symbol); scope_by_range.append((node.start_byte, node.end_byte, symbol))
        elif node.type == "class_declaration":
            symbol = _add_named_symbol(analysis, fnode.id, node, source_bytes, path, content_hash, "CLASS", exported, False)
            if symbol:
                heritage = _class_extends(node, source_bytes)
                if heritage:
                    symbol.properties["extends"] = heritage
                    parent = Node(id=f"CLASS-{stable_id('unresolved', heritage)}", kind="CLASS", name=heritage, properties={"unresolved": True}, classification=Classification.INFERRED.value)
                    analysis.nodes.append(parent)
                    analysis.edges.append(Edge(
                        id=f"EDGE-{stable_id('EXTENDS', symbol.id, parent.id)}", kind="DEPENDS_ON", source=symbol.id, target=parent.id,
                        properties={"relationship": "extends", "target": heritage}, classification=Classification.INFERRED.value, confidence=0.75,
                        evidence=symbol.evidence[:1],
                    ))
                symbols.append(symbol); scope_by_range.append((node.start_byte, node.end_byte, symbol))
                _add_methods(analysis, symbol, node, source_bytes, path, content_hash, symbols, scope_by_range)
        elif node.type in {"interface_declaration", "type_alias_declaration", "enum_declaration"}:
            kind = {"interface_declaration": "INTERFACE", "type_alias_declaration": "TYPE_ALIAS", "enum_declaration": "ENUM"}[node.type]
            symbol = _add_named_symbol(analysis, fnode.id, node, source_bytes, path, content_hash, kind, exported, False)
            if symbol:
                symbols.append(symbol)
        elif node.type == "variable_declarator":
            value = _field(node, "value")
            if value is not None and value.type == "arrow_function":
                name_node = _field(node, "name")
                name = _text(name_node, source_bytes) if name_node else None
                if name:
                    symbol = _make_symbol(path, content_hash, "FUNCTION", name, node, exported or _is_within_export(node), _is_async(value), analyzer="javascript")
                    symbol.properties["function_kind"] = "arrow"
                    symbols.append(symbol); analysis.nodes.append(symbol); add_contains(analysis, fnode.id, symbol); scope_by_range.append((value.start_byte, value.end_byte, symbol))
        elif node.type == "assignment_expression":
            _add_commonjs_export(analysis, fnode.id, node, source_bytes, path, content_hash, symbols)

    _add_routes_and_relationships(analysis, fnode, tree.root_node, source_bytes, path, content_hash, scope_by_range)
    _add_env_references(analysis, fnode, tree.root_node, source_bytes, path, content_hash)
    _add_next_routes(analysis, fnode, tree.root_node, source_bytes, path, content_hash)
    return analysis

def _parse_tree(source: str, language: str):
    if Parser is None or Language is None:
        return None
    try:
        parser = Parser()
        if language == "typescript":
            parser.language = Language(tree_sitter_typescript.language_typescript())
        else:
            parser.language = Language(tree_sitter_javascript.language())
        return parser.parse(source.encode("utf-8"))
    except Exception:
        return None

def _walk(node: TSNode) -> Iterable[TSNode]:
    yield node
    for child in node.children:
        yield from _walk(child)

def _text(node: TSNode | None, source_bytes: bytes) -> str | None:
    if node is None:
        return None
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace").strip()

def _string_value(node: TSNode | None, source_bytes: bytes) -> str | None:
    if node is None or node.type != "string":
        return None
    for child in node.children:
        if child.type == "string_fragment":
            return _text(child, source_bytes)
    raw = _text(node, source_bytes)
    return raw[1:-1] if raw and len(raw) >= 2 and raw[0] in {"'", '"', "`"} else raw

def _field(node: TSNode, name: str) -> TSNode | None:
    try:
        return node.child_by_field_name(name)
    except Exception:
        return None

def _line_from_node(node: TSNode) -> int:
    return int(node.start_point[0]) + 1

def _is_within_export(node: TSNode) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type == "export_statement":
            return True
        parent = parent.parent
    return False

def _is_async(node: TSNode) -> bool:
    return any(child.type == "async" for child in node.children)

def _name_from_declaration(node: TSNode, source_bytes: bytes) -> str | None:
    direct = _field(node, "name")
    if direct is not None:
        return _text(direct, source_bytes)
    for child in node.children:
        if child.type in {"identifier", "type_identifier", "property_identifier"}:
            return _text(child, source_bytes)
    return None

def _make_symbol(path: str, content_hash: str, kind: str, name: str, node: TSNode, exported: bool, is_async: bool, *, analyzer: str) -> Node:
    line = _line_from_node(node)
    props = {"qualified_name": name, "exported": exported}
    if is_async:
        props["async"] = True
    if kind == "INTERFACE":
        props["symbol_kind"] = "interface"
    elif kind == "TYPE_ALIAS":
        props["symbol_kind"] = "type_alias"
    elif kind == "ENUM":
        props["symbol_kind"] = "enum"
    return Node(
        id=f"{kind}-{stable_id(path, name, str(line))}", kind=kind, name=name, path=path,
        properties=props,
        evidence=[evidence(path, content_hash, line, name, analyzer=analyzer)],
    )

def _add_named_symbol(analysis: FileAnalysis, parent_id: str, node: TSNode, source_bytes: bytes, path: str, content_hash: str, kind: str, exported: bool, is_async: bool) -> Node | None:
    name = _name_from_declaration(node, source_bytes)
    if not name:
        return None
    item = _make_symbol(path, content_hash, kind, name, node, exported, is_async, analyzer="javascript")
    analysis.nodes.append(item)
    add_contains(analysis, parent_id, item)
    return item

def _module_node(analysis: FileAnalysis, fnode: Node, module: str, imported_names: list[dict], node: TSNode, source_bytes: bytes, path: str, content_hash: str, language: str, import_kind: str = "static") -> None:
    line = _line_from_node(node)
    target = Node(
        id=f"MODULE-{stable_id(module)}", kind="MODULE", name=module,
        properties={"external": not module.startswith((".", "/")), "language": language, "imported_names": imported_names, "import_kind": import_kind},
        evidence=[evidence(path, content_hash, line, note=f"import {module}", analyzer="javascript")],
    )
    analysis.nodes.append(target)
    analysis.edges.append(Edge(
        id=f"EDGE-{stable_id('IMPORTS', fnode.id, target.id, str(line), import_kind)}",
        kind="IMPORTS", source=fnode.id, target=target.id,
        properties={"module": module, "imported_names": imported_names, "import_kind": import_kind},
        evidence=target.evidence[:],
    ))
    for prefix, stack in STACK_MODULES.items():
        if module == prefix or module.startswith(prefix + "/"):
            analysis.stack.add(stack)

def _add_import_statement(analysis: FileAnalysis, fnode: Node, node: TSNode, source_bytes: bytes, path: str, content_hash: str, language: str) -> None:
    module = _string_value(_field(node, "source"), source_bytes)
    if module is None:
        module = next((_string_value(child, source_bytes) for child in node.children if child.type == "string"), None)
    if not module:
        return
    imported_names: list[dict] = []
    clause = next((child for child in node.children if child.type == "import_clause"), None)
    if clause is None:
        imported_names.append({"name": "*", "alias": "*", "kind": "side-effect"})
    else:
        for child in clause.children:
            if child.type == "identifier":
                imported_names.append({"name": "default", "alias": _text(child, source_bytes), "kind": "default"})
            elif child.type == "namespace_import":
                alias = next((_text(grand, source_bytes) for grand in child.children if grand.type == "identifier"), None)
                imported_names.append({"name": "*", "alias": alias, "kind": "namespace"})
            elif child.type == "named_imports":
                for spec in [grand for grand in child.children if grand.type == "import_specifier"]:
                    ids = [_text(grand, source_bytes) for grand in spec.children if grand.type == "identifier"]
                    if ids:
                        imported_names.append({"name": ids[0], "alias": ids[-1], "kind": "named"})
    _module_node(analysis, fnode, module, imported_names, node, source_bytes, path, content_hash, language)

def _add_call_import_if_static(analysis: FileAnalysis, fnode: Node, node: TSNode, source_bytes: bytes, path: str, content_hash: str, language: str) -> None:
    callee = node.children[0] if node.children else None
    callee_text = _text(callee, source_bytes)
    if callee_text not in {"require", "import"}:
        return
    args = next((child for child in node.children if child.type == "arguments"), None)
    module = next((_string_value(child, source_bytes) for child in (args.children if args else []) if child.type == "string"), None)
    if module:
        kind = "require" if callee_text == "require" else "dynamic"
        _module_node(analysis, fnode, module, [{"name": "*", "alias": "*", "kind": kind}], node, source_bytes, path, content_hash, language, import_kind=kind)

def _add_export_statement(analysis: FileAnalysis, fnode: Node, node: TSNode, source_bytes: bytes, path: str, content_hash: str, language: str) -> None:
    module = next((_string_value(child, source_bytes) for child in node.children if child.type == "string"), None)
    names: list[dict] = []
    is_default = any(child.type == "default" for child in node.children)
    is_star = any(_text(child, source_bytes) == "*" for child in node.children)
    for child in node.children:
        if child.type == "export_clause":
            for spec in [grand for grand in child.children if grand.type == "export_specifier"]:
                ids = [_text(grand, source_bytes) for grand in spec.children if grand.type == "identifier"]
                if ids:
                    names.append({"name": ids[0], "alias": ids[-1], "kind": "named"})
    if is_default:
        names.append({"name": "default", "alias": "default", "kind": "default"})
    if is_star:
        names.append({"name": "*", "alias": "*", "kind": "export-star"})
    if module:
        _module_node(analysis, fnode, module, names, node, source_bytes, path, content_hash, language, import_kind="re-export")
    if names:
        fnode.properties.setdefault("exports", []).extend(names)

def _class_extends(node: TSNode, source_bytes: bytes) -> str | None:
    for child in node.children:
        if child.type == "class_heritage":
            for grand in _walk(child):
                if grand.type in {"identifier", "type_identifier"}:
                    return _text(grand, source_bytes)
    return None

def _add_methods(analysis: FileAnalysis, class_node: Node, class_decl: TSNode, source_bytes: bytes, path: str, content_hash: str, symbols: list[Node], scope_by_range: list[tuple[int, int, Node]]) -> None:
    for node in _walk(class_decl):
        if node.type != "method_definition":
            continue
        name = _name_from_declaration(node, source_bytes)
        if not name:
            continue
        line = _line_from_node(node)
        item = Node(
            id=f"METHOD-{stable_id(path, class_node.id, name, str(line))}", kind="METHOD", name=name, path=path,
            properties={
                "qualified_name": f"{class_node.name}.{name}",
                "exported": class_node.properties.get("exported", False),
                "constructor": name == "constructor",
                "static": any(child.type == "static" for child in node.children),
                "async": _is_async(node),
            },
            evidence=[evidence(path, content_hash, line, name, analyzer="javascript")],
        )
        symbols.append(item); analysis.nodes.append(item); add_contains(analysis, class_node.id, item); scope_by_range.append((node.start_byte, node.end_byte, item))
        _maybe_repository_table_edge(analysis, item, class_node.name, path, content_hash, line)

def _add_commonjs_export(analysis: FileAnalysis, parent_id: str, node: TSNode, source_bytes: bytes, path: str, content_hash: str, symbols: list[Node]) -> None:
    left = _field(node, "left") or (node.children[0] if node.children else None)
    left_text = _text(left, source_bytes) or ""
    if not (left_text == "module.exports" or left_text.startswith("exports.")):
        return
    name = left_text.split(".", 1)[1] if left_text.startswith("exports.") else "module.exports"
    line = _line_from_node(node)
    item = Node(
        id=f"FUNCTION-{stable_id(path, 'commonjs-export', name, str(line))}", kind="FUNCTION", name=name, path=path,
        properties={"exported": True, "commonjs": True},
        evidence=[evidence(path, content_hash, line, name, "CommonJS export", analyzer="javascript")],
    )
    symbols.append(item); analysis.nodes.append(item); add_contains(analysis, parent_id, item)

def _scope_for(node: TSNode, scopes: list[tuple[int, int, Node]]) -> Node:
    containing = [scope for scope in scopes if scope[0] <= node.start_byte and node.end_byte <= scope[1]]
    return min(containing, key=lambda item: item[1] - item[0])[2]

def _call_name(node: TSNode, source_bytes: bytes) -> str | None:
    if not node.children:
        return None
    callee = node.children[0]
    if callee.type in {"identifier", "member_expression"}:
        return _text(callee, source_bytes)
    return None

def _add_routes_and_relationships(analysis: FileAnalysis, fnode: Node, root: TSNode, source_bytes: bytes, path: str, content_hash: str, scopes: list[tuple[int, int, Node]]) -> None:
    for node in _walk(root):
        if node.type == "new_expression":
            name = next((_text(child, source_bytes) for child in node.children if child.type in {"identifier", "type_identifier"}), None)
            if name:
                scope = _scope_for(node, scopes)
                target = Node(id=f"CLASS-{stable_id('unresolved', name)}", kind="CLASS", name=name, properties={"unresolved": True}, classification=Classification.INFERRED.value)
                analysis.nodes.append(target)
                analysis.edges.append(Edge(
                    id=f"EDGE-{stable_id('CALLS', scope.id, target.id, str(_line_from_node(node)))}", kind="CALLS", source=scope.id, target=target.id,
                    classification=Classification.INFERRED.value, confidence=0.7,
                    evidence=[evidence(path, content_hash, _line_from_node(node), scope.name, f"constructor usage {name}", analyzer="javascript")],
                ))
        if node.type != "call_expression":
            continue
        name = _call_name(node, source_bytes)
        if not name or name in {"require", "import"} or name.split(".")[0] in {"if", "for", "while", "switch", "function", "catch"}:
            continue
        args = next((child for child in node.children if child.type == "arguments"), None)
        first_string = next((_string_value(child, source_bytes) for child in (args.children if args else []) if child.type == "string"), None)
        tail = name.split(".")[-1].lower()
        line = _line_from_node(node)
        if first_string and tail in {"get", "post", "put", "patch", "delete", "options", "head"}:
            handler = None
            arg_children = [child for child in args.children if child.type not in {"(", ")", ","}]
            if len(arg_children) >= 2:
                handler = _text(arg_children[1], source_bytes)
            endpoint = Node(
                id=f"API-{stable_id(path, tail.upper(), first_string, str(line))}", kind="API_ENDPOINT",
                name=f"{tail.upper()} {first_string}", path=path, properties={"method": tail.upper(), "path": first_string, "handler": handler},
                evidence=[evidence(path, content_hash, line, note="HTTP route registration", analyzer="javascript")],
            )
            analysis.nodes.append(endpoint)
            analysis.edges.append(Edge(id=f"EDGE-{stable_id('EXPOSES', fnode.id, endpoint.id)}", kind="EXPOSES", source=fnode.id, target=endpoint.id, evidence=endpoint.evidence[:]))
            continue
        if first_string and tail in {"emit", "publish", "send", "on", "subscribe", "consume"}:
            kind = "PUBLISHES" if tail in {"emit", "publish", "send"} else "CONSUMES"
            event = Node(
                id=f"EVENT-{stable_id(first_string)}", kind="EVENT", name=first_string,
                evidence=[evidence(path, content_hash, line, note=f"{kind.lower()} event", analyzer="javascript")],
            )
            analysis.nodes.append(event)
            analysis.edges.append(Edge(id=f"EDGE-{stable_id(kind, fnode.id, event.id, str(line))}", kind=kind, source=fnode.id, target=event.id, evidence=event.evidence[:]))
            continue
        target = Node(id=f"FUNCTION-{stable_id('unresolved', name)}", kind="FUNCTION", name=name, properties={"unresolved": True}, classification=Classification.INFERRED.value)
        scope = _scope_for(node, scopes)
        analysis.nodes.append(target)
        analysis.edges.append(Edge(
            id=f"EDGE-{stable_id('CALLS', scope.id, target.id, str(line))}", kind="CALLS", source=scope.id, target=target.id,
            classification=Classification.INFERRED.value, confidence=0.65,
            evidence=[evidence(path, content_hash, line, scope.name, f"AST call {name}", analyzer="javascript")],
        ))

def _add_env_references(analysis: FileAnalysis, fnode: Node, root: TSNode, source_bytes: bytes, path: str, content_hash: str) -> None:
    for node in _walk(root):
        raw = _text(node, source_bytes) or ""
        key = None
        if node.type == "member_expression":
            if raw.startswith("process.env."):
                key = raw.rsplit(".", 1)[-1]
            elif raw.startswith("import.meta.env."):
                key = raw.rsplit(".", 1)[-1]
        elif node.type == "subscript_expression" and raw.startswith("process.env["):
            key = next((_string_value(child, source_bytes) for child in node.children if child.type == "string"), None)
        if not key:
            continue
        line = _line_from_node(node)
        item = Node(
            id=f"CONFIG-{stable_id(key)}", kind="CONFIGURATION_KEY", name=key,
            properties={"sensitive_candidate": any(x in key.upper() for x in ("SECRET", "TOKEN", "PASSWORD", "KEY"))},
            evidence=[evidence(path, content_hash, line, note="environment reference", analyzer="javascript")],
        )
        analysis.nodes.append(item)
        analysis.edges.append(Edge(id=f"EDGE-{stable_id('CONFIGURED_BY', fnode.id, item.id, str(line))}", kind="CONFIGURED_BY", source=fnode.id, target=item.id, evidence=item.evidence[:]))

def _add_next_routes(analysis: FileAnalysis, fnode: Node, root: TSNode, source_bytes: bytes, path: str, content_hash: str) -> None:
    if not _looks_like_next_route(path):
        return
    analysis.stack.add("Next.js")
    route_path = _next_route_path(path)
    for node in _walk(root):
        if node.type != "function_declaration" or not _is_within_export(node):
            continue
        name = _name_from_declaration(node, source_bytes)
        if name not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
            continue
        line = _line_from_node(node)
        endpoint = Node(
            id=f"API-{stable_id(path, name, route_path, str(line))}", kind="API_ENDPOINT",
            name=f"{name} {route_path}", path=path, properties={"method": name, "path": route_path, "framework": "Next.js"},
            evidence=[evidence(path, content_hash, line, name, "Next.js route handler export", analyzer="javascript")],
        )
        analysis.nodes.append(endpoint)
        analysis.edges.append(Edge(id=f"EDGE-{stable_id('EXPOSES', fnode.id, endpoint.id)}", kind="EXPOSES", source=fnode.id, target=endpoint.id, evidence=endpoint.evidence[:]))

def _line(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1

def _imported_names(clause: str) -> list[dict]:
    clause = clause.strip()
    if not clause:
        return []
    if clause.startswith("* as "):
        return [{"name": "*", "alias": clause.split(None, 2)[-1], "kind": "namespace"}]
    result = []
    before_brace = clause.split("{", 1)[0].strip().strip(",")
    if before_brace:
        result.append({"name": "default", "alias": before_brace, "kind": "default"})
    if "{" in clause and "}" in clause:
        names = clause.split("{", 1)[1].split("}", 1)[0]
        for item in names.split(","):
            item = item.strip()
            if not item:
                continue
            if " as " in item:
                name, alias = [part.strip() for part in item.split(" as ", 1)]
            else:
                name, alias = item, item
            result.append({"name": name, "alias": alias, "kind": "named"})
    return result

def _is_exported(source: str, offset: int) -> bool:
    prefix = source[max(0, offset - 32):offset]
    return "export" in prefix

def _class_ranges(source: str, symbols: list[Node]) -> list[tuple[Node, int, int]]:
    by_name = {node.name: node for node in symbols if node.kind == "CLASS"}
    ranges = []
    for match in CLASS_RE.finditer(source):
        node = by_name.get(match.group(1))
        brace = source.find("{", match.end())
        if not node or brace == -1:
            continue
        end = _matching_brace(source, brace)
        if end != -1:
            ranges.append((node, brace + 1, end))
    return ranges

def _matching_brace(source: str, start: int) -> int:
    depth = 0
    quote = ""
    escaped = False
    for index in range(start, len(source)):
        ch = source[index]
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = ""
            continue
        if ch in {"'", '"', "`"}:
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1

def _maybe_repository_table_edge(analysis: FileAnalysis, method: Node, class_name: str, path: str, content_hash: str, line: int) -> None:
    if "repository" not in class_name.lower() and "repo" not in class_name.lower():
        return
    base = class_name.removesuffix("Repository").removesuffix("Repo").lower()
    table_name = base + ("s" if not base.endswith("s") else "")
    table = Node(
        id=f"TABLE-{stable_id(table_name)}", kind="TABLE", name=table_name, path=path,
        properties={"inferred_from_repository": class_name},
        classification=Classification.INFERRED.value,
        evidence=[evidence(path, content_hash, line, method.name, "repository method implies table access", analyzer="javascript")],
    )
    analysis.nodes.append(table)
    kind = "WRITES" if any(word in method.name.lower() for word in ("save", "create", "insert", "update", "delete")) else "READS"
    analysis.edges.append(Edge(
        id=f"EDGE-{stable_id(kind, method.id, table.id, str(line))}", kind=kind,
        source=method.id, target=table.id, classification=Classification.INFERRED.value, confidence=0.58,
        evidence=table.evidence[:],
    ))

def _looks_like_next_route(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.endswith("/route.ts") or normalized.endswith("/route.tsx") or normalized.endswith("/route.js")

def _next_route_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    if "app" in parts:
        app_index = parts.index("app")
        route_parts = [part for part in parts[app_index + 1:-1] if not (part.startswith("(") and part.endswith(")"))]
        cleaned = [part for part in route_parts if not part.startswith("@")]
        return "/" + "/".join(cleaned).replace("[", ":").replace("]", "") if cleaned else "/"
    return "<next-route-path>"
