from __future__ import annotations

import re

from ..models import Classification, Edge, FileAnalysis, Node
from .base import add_contains, evidence, file_node, stable_id

IMPORT_RE = re.compile(r"""(?:import\s+(?:[^'"]+?\s+from\s+)?|require\s*\()\s*['"]([^'"]+)['"]""")
FUNCTION_RE = re.compile(r"""(?m)^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(""")
ARROW_RE = re.compile(r"""(?m)^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>""")
CLASS_RE = re.compile(r"""(?m)^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)""")
COMMONJS_EXPORT_RE = re.compile(r"""(?m)^\s*(?:module\.exports|exports\.([A-Za-z_$][\w$]*))\s*=""")
ROUTE_RE = re.compile(r"""\b(?:app|router|server)\.(get|post|put|patch|delete|options|head)\s*\(\s*['"`]([^'"`]+)['"`]""", re.IGNORECASE)
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
    analysis = FileAnalysis(path=path, content_hash=content_hash)
    fnode = file_node(path, content_hash, language)
    analysis.nodes.append(fnode)
    for match in IMPORT_RE.finditer(source):
        module, line = match.group(1), _line(source, match.start())
        target = Node(
            id=f"MODULE-{stable_id(module)}", kind="MODULE", name=module,
            properties={"external": not module.startswith((".", "/"))},
            evidence=[evidence(path, content_hash, line, note=f"import {module}")],
        )
        analysis.nodes.append(target)
        analysis.edges.append(Edge(
            id=f"EDGE-{stable_id('IMPORTS', fnode.id, target.id, str(line))}",
            kind="IMPORTS", source=fnode.id, target=target.id, evidence=target.evidence[:],
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
                evidence=[evidence(path, content_hash, line, name)],
            )
            symbols.append(item)
            analysis.nodes.append(item)
            add_contains(analysis, fnode.id, item)
    for match in COMMONJS_EXPORT_RE.finditer(source):
        name = match.group(1) or "module.exports"
        line = _line(source, match.start())
        item = Node(
            id=f"FUNCTION-{stable_id(path, 'commonjs-export', name, str(line))}", kind="FUNCTION", name=name, path=path,
            properties={"exported": True, "commonjs": True},
            evidence=[evidence(path, content_hash, line, name, "CommonJS export")],
        )
        symbols.append(item)
        analysis.nodes.append(item)
        add_contains(analysis, fnode.id, item)
    for match in ROUTE_RE.finditer(source):
        method, route, line = match.group(1).upper(), match.group(2), _line(source, match.start())
        endpoint = Node(
            id=f"API-{stable_id(path, method, route, str(line))}", kind="API_ENDPOINT",
            name=f"{method} {route}", path=path, properties={"method": method, "path": route},
            evidence=[evidence(path, content_hash, line, note="HTTP route registration")],
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
                evidence=[evidence(path, content_hash, line, method, "Next.js route handler export")],
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
            evidence=[evidence(path, content_hash, line, note="process.env reference")],
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
            evidence=[evidence(path, content_hash, line, scope.name, f"syntactic call {name}")],
        ))
    for regex, kind in ((EVENT_PUBLISH_RE, "PUBLISHES"), (EVENT_CONSUME_RE, "CONSUMES")):
        for match in regex.finditer(source):
            event_name, line = match.group(1), _line(source, match.start())
            event = Node(
                id=f"EVENT-{stable_id(event_name)}", kind="EVENT", name=event_name,
                evidence=[evidence(path, content_hash, line, note=f"{kind.lower()} event")],
            )
            analysis.nodes.append(event)
            analysis.edges.append(Edge(
                id=f"EDGE-{stable_id(kind, fnode.id, event.id, str(line))}",
                kind=kind, source=fnode.id, target=event.id, evidence=event.evidence[:],
            ))
    return analysis

def _line(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1

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
