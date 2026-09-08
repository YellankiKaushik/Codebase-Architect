from __future__ import annotations

import ast
from pathlib import Path

from ..models import AnalyzerCapability, Classification, Edge, FileAnalysis, Node
from .base import add_contains, evidence, file_node, stable_id

FRAMEWORK_IMPORTS = {
    "fastapi": "FastAPI", "flask": "Flask", "django": "Django",
    "sqlalchemy": "SQLAlchemy", "pydantic": "Pydantic", "celery": "Celery",
    "redis": "Redis", "psycopg": "PostgreSQL", "psycopg2": "PostgreSQL",
    "pymongo": "MongoDB",
}

class PythonAnalyzer(ast.NodeVisitor):
    def __init__(self, path: str, content_hash: str, source: str):
        self.path, self.content_hash, self.source = path, content_hash, source
        self.analysis = FileAnalysis(
            path=path, content_hash=content_hash,
            analyzer="python", capability=AnalyzerCapability.AST.value, backend="python-ast",
        )
        self.file = file_node(path, content_hash, "python", analyzer="python", capability=AnalyzerCapability.AST.value, backend="python-ast")
        self.analysis.nodes.append(self.file)
        self.scope_stack: list[Node] = [self.file]
        self.import_aliases: dict[str, str] = {}

    @property
    def scope(self) -> Node:
        return self.scope_stack[-1]

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.import_aliases[alias.asname or alias.name.split(".")[0]] = alias.name
            self._import(alias.name, node.lineno, imported_name=None, alias=alias.asname)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        if module:
            for alias in node.names:
                local = alias.asname or alias.name
                self.import_aliases[local] = f"{module}.{alias.name}".strip(".")
            imported = [{"name": a.name, "alias": a.asname} for a in node.names]
            self._import(module, node.lineno, imported_names=imported)
        self.generic_visit(node)

    def _import(self, module: str, line: int, imported_name: str | None = None, alias: str | None = None, imported_names: list[dict] | None = None) -> None:
        root = module.lstrip(".").split(".")[0]
        target_id = f"MODULE-{stable_id(module)}"
        target = Node(
            id=target_id, kind="MODULE", name=module,
            properties={
                "external": not module.startswith("."),
                "language": "python",
                "imported_name": imported_name,
                "alias": alias,
                "imported_names": imported_names or [],
            },
            evidence=[evidence(self.path, self.content_hash, line, note=f"import {module}", analyzer="python")],
        )
        self.analysis.nodes.append(target)
        self.analysis.edges.append(Edge(
            id=f"EDGE-{stable_id('IMPORTS', self.file.id, target_id, str(line))}",
            kind="IMPORTS", source=self.file.id, target=target_id,
            properties={"module": module, "imported_names": imported_names or [], "alias": alias},
            evidence=target.evidence[:],
        ))
        if root in FRAMEWORK_IMPORTS:
            self.analysis.stack.add(FRAMEWORK_IMPORTS[root])

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        item = Node(
            id=f"CLASS-{stable_id(self.path, node.name, str(node.lineno))}",
            kind="CLASS", name=node.name, path=self.path,
            properties={"bases": [self._name(base) for base in node.bases], "qualified_name": node.name, "exported": not node.name.startswith("_")},
            evidence=[evidence(self.path, self.content_hash, node.lineno, node.name, analyzer="python")],
        )
        self.analysis.nodes.append(item)
        add_contains(self.analysis, self.scope.id, item)
        for base_name in item.properties.get("bases", []):
            if base_name:
                target = Node(
                    id=f"CLASS-{stable_id('unresolved', base_name)}", kind="CLASS", name=base_name,
                    properties={"unresolved": True}, classification=Classification.INFERRED.value,
                )
                self.analysis.nodes.append(target)
                self.analysis.edges.append(Edge(
                    id=f"EDGE-{stable_id('INHERITS', item.id, target.id, str(node.lineno))}",
                    kind="DEPENDS_ON", source=item.id, target=target.id,
                    properties={"relationship": "inherits"},
                    classification=Classification.INFERRED.value, confidence=0.7,
                    evidence=[evidence(self.path, self.content_hash, node.lineno, node.name, f"base {base_name}", analyzer="python")],
                ))
        self._maybe_model_table(item, node)
        self.scope_stack.append(item)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function(node)

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        owner = self.scope
        kind = "METHOD" if owner.kind == "CLASS" else "FUNCTION"
        item = Node(
            id=f"{kind}-{stable_id(self.path, owner.id, node.name, str(node.lineno))}",
            kind=kind, name=node.name, path=self.path,
            properties={
                "async": isinstance(node, ast.AsyncFunctionDef),
                "arguments": [arg.arg for arg in node.args.args],
                "qualified_name": f"{owner.name}.{node.name}" if owner.kind == "CLASS" else node.name,
                "exported": not node.name.startswith("_"),
            },
            evidence=[evidence(self.path, self.content_hash, node.lineno, node.name, analyzer="python")],
        )
        self.analysis.nodes.append(item)
        add_contains(self.analysis, self.scope.id, item)
        for decorator in node.decorator_list:
            route = self._route_from_decorator(decorator)
            if route:
                method, route_path = route
                endpoint = Node(
                    id=f"API-{stable_id(self.path, method, route_path, node.name)}",
                    kind="API_ENDPOINT", name=f"{method} {route_path}", path=self.path,
                    properties={"method": method, "path": route_path, "handler": node.name},
                    evidence=[evidence(self.path, self.content_hash, getattr(decorator, "lineno", node.lineno), node.name, analyzer="python")],
                )
                self.analysis.nodes.append(endpoint)
                self.analysis.edges.append(Edge(
                    id=f"EDGE-{stable_id('EXPOSES', item.id, endpoint.id)}",
                    kind="EXPOSES", source=item.id, target=endpoint.id, evidence=endpoint.evidence[:],
                ))
        self.scope_stack.append(item)
        for child in node.body:
            self.visit(child)
        self._maybe_repository_table_edges(owner, item, node)
        self.scope_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        name = self._name(node.func)
        if name:
            resolved_name = self.import_aliases.get(name.split(".", 1)[0])
            target = Node(
                id=f"FUNCTION-{stable_id('unresolved', name)}", kind="FUNCTION", name=name,
                properties={"unresolved": True, "resolved_import": resolved_name}, classification=Classification.INFERRED.value,
            )
            self.analysis.nodes.append(target)
            self.analysis.edges.append(Edge(
                id=f"EDGE-{stable_id('CALLS', self.scope.id, target.id, str(node.lineno))}",
                kind="CALLS", source=self.scope.id, target=target.id,
                classification=Classification.INFERRED.value, confidence=0.65,
                evidence=[evidence(self.path, self.content_hash, node.lineno, self.scope.name, f"call {name}", analyzer="python")],
            ))
        if name in {"os.getenv", "os.environ.get"} and node.args and isinstance(node.args[0], ast.Constant):
            self._config_key(str(node.args[0].value), node.lineno)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if self._name(node.value) == "os.environ":
            value = node.slice
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                self._config_key(value.value, node.lineno)
        self.generic_visit(node)

    def _config_key(self, key: str, line: int) -> None:
        item = Node(
            id=f"CONFIG-{stable_id(key)}", kind="CONFIGURATION_KEY", name=key,
            properties={"sensitive_candidate": any(x in key.upper() for x in ("SECRET", "TOKEN", "PASSWORD", "KEY"))},
            evidence=[evidence(self.path, self.content_hash, line, self.scope.name, analyzer="python")],
        )
        self.analysis.nodes.append(item)
        self.analysis.edges.append(Edge(
            id=f"EDGE-{stable_id('CONFIGURED_BY', self.scope.id, item.id, str(line))}",
            kind="CONFIGURED_BY", source=self.scope.id, target=item.id, evidence=item.evidence[:],
        ))

    def _route_from_decorator(self, decorator: ast.expr) -> tuple[str, str] | None:
        if not isinstance(decorator, ast.Call):
            return None
        name = self._name(decorator.func)
        if not name:
            return None
        method = name.split(".")[-1].upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
            return None
        if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
            return method, decorator.args[0].value
        return method, "<dynamic-path>"

    @staticmethod
    def _name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            left = PythonAnalyzer._name(node.value)
            return f"{left}.{node.attr}" if left else node.attr
        if isinstance(node, ast.Call):
            return PythonAnalyzer._name(node.func)
        if isinstance(node, ast.Subscript):
            return PythonAnalyzer._name(node.value)
        return ""

    def _maybe_model_table(self, item: Node, node: ast.ClassDef) -> None:
        bases = " ".join(item.properties.get("bases", []))
        if "Base" not in bases and "Model" not in bases:
            return
        table_name = None
        for child in node.body:
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name) and target.id == "__tablename__" and isinstance(child.value, ast.Constant):
                        table_name = str(child.value.value)
        if not table_name:
            return
        table = Node(
            id=f"TABLE-{stable_id(table_name)}", kind="TABLE", name=table_name, path=self.path,
            properties={"orm": "SQLAlchemy", "model": item.name},
            evidence=[evidence(self.path, self.content_hash, node.lineno, item.name, "SQLAlchemy table model", analyzer="python")],
        )
        self.analysis.nodes.append(table)
        self.analysis.edges.append(Edge(
            id=f"EDGE-{stable_id('DEPENDS_ON', item.id, table.id)}", kind="DEPENDS_ON",
            source=item.id, target=table.id, evidence=table.evidence[:],
        ))

    def _maybe_repository_table_edges(self, owner: Node, item: Node, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if "repository" not in (owner.name + item.name).lower() and "repo" not in (owner.name + item.name).lower():
            return
        table_name = _pluralize(owner.name.removesuffix("Repository").removesuffix("Repo").lower())
        table = Node(
            id=f"TABLE-{stable_id(table_name)}", kind="TABLE", name=table_name, path=self.path,
            properties={"inferred_from_repository": owner.name},
            classification=Classification.INFERRED.value,
            evidence=[evidence(self.path, self.content_hash, node.lineno, item.name, "repository method implies table access", analyzer="python")],
        )
        self.analysis.nodes.append(table)
        kind = "WRITES" if any(word in item.name.lower() for word in ("save", "create", "insert", "update", "delete")) else "READS"
        self.analysis.edges.append(Edge(
            id=f"EDGE-{stable_id(kind, item.id, table.id, str(node.lineno))}", kind=kind,
            source=item.id, target=table.id, classification=Classification.INFERRED.value, confidence=0.6,
            evidence=table.evidence[:],
        ))

def analyze(path: str, content_hash: str, source: str) -> FileAnalysis:
    analyzer = PythonAnalyzer(path, content_hash, source)
    try:
        tree = ast.parse(source, filename=Path(path).name)
    except SyntaxError as exc:
        analyzer.analysis.warnings.append(f"Python syntax error at line {exc.lineno}: {exc.msg}")
        return analyzer.analysis
    analyzer.visit(tree)
    return analyzer.analysis

def _pluralize(value: str) -> str:
    if not value:
        return "unknown"
    if value.endswith("y"):
        return value[:-1] + "ies"
    if value.endswith("s"):
        return value
    return value + "s"
