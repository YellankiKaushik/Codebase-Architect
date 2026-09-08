from __future__ import annotations

import json
import re
from pathlib import Path

from ..models import AnalyzerCapability, Edge, FileAnalysis, Node
from .base import evidence, file_node, stable_id

DATASTORE_DEPENDENCIES = {
    "pg": ("PostgreSQL", "DATABASE"), "psycopg": ("PostgreSQL", "DATABASE"),
    "psycopg2": ("PostgreSQL", "DATABASE"), "mysql": ("MySQL", "DATABASE"),
    "mysql2": ("MySQL", "DATABASE"), "pymongo": ("MongoDB", "DATABASE"),
    "mongoose": ("MongoDB", "DATABASE"), "redis": ("Redis", "DATABASE"),
    "sqlalchemy": ("SQL Database", "DATABASE"), "prisma": ("Database via Prisma", "DATABASE"),
}
KNOWN_STACK = {
    "fastapi": "FastAPI", "flask": "Flask", "django": "Django", "express": "Express",
    "fastify": "Fastify", "@nestjs/core": "NestJS", "next": "Next.js", "react": "React",
    "typescript": "TypeScript", "pytest": "pytest", "jest": "Jest", "vitest": "Vitest",
}

def analyze(path: str, content_hash: str, source: str, language: str) -> FileAnalysis:
    analysis = FileAnalysis(path=path, content_hash=content_hash, analyzer="config-files", capability=AnalyzerCapability.STRUCTURAL.value, backend="text-json")
    fnode = file_node(path, content_hash, language, analyzer="config-files", capability=AnalyzerCapability.STRUCTURAL.value, backend="text-json")
    analysis.nodes.append(fnode)
    name = Path(path).name
    if name == "package.json":
        _package_json(analysis, fnode, path, content_hash, source)
    elif name == "requirements.txt":
        _requirements(analysis, fnode, path, content_hash, source)
    elif name == "pyproject.toml":
        _pyproject_text(analysis, fnode, path, content_hash, source)
    elif name == "Dockerfile":
        _dockerfile(analysis, path, content_hash, source)
    elif name in {"docker-compose.yml", "docker-compose.yaml"}:
        analysis.stack.add("Docker Compose")
        _compose_text(analysis, fnode, path, content_hash, source)
    elif path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml")):
        analysis.stack.add("GitHub Actions")
        analysis.nodes.append(Node(
            id=f"INFRA-{stable_id(path)}", kind="INFRA_RESOURCE", name=Path(path).stem, path=path,
            properties={"type": "github-actions-workflow"},
            evidence=[evidence(path, content_hash, 1, note="workflow file")],
        ))
    return analysis

def _package_json(analysis, fnode, path, content_hash, source):
    try:
        raw = json.loads(source)
    except json.JSONDecodeError as exc:
        analysis.warnings.append(f"Invalid package.json: {exc}")
        return
    dependencies = {}
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        dependencies.update(raw.get(section, {}) or {})
    for dep, version in dependencies.items():
        _dependency(analysis, fnode, path, content_hash, dep, str(version), 1)
    for script_name in (raw.get("scripts", {}) or {}):
        if script_name.lower().startswith(("test", "lint", "build", "start", "dev")):
            analysis.stack.add(f"npm script:{script_name}")

def _requirements(analysis, fnode, path, content_hash, source):
    for lineno, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(("-", "git+")):
            continue
        dep = re.split(r"[<>=!~\[\s]", stripped, maxsplit=1)[0].strip()
        if dep:
            _dependency(analysis, fnode, path, content_hash, dep, stripped, lineno)

def _pyproject_text(analysis, fnode, path, content_hash, source):
    for dep, stack in KNOWN_STACK.items():
        if re.search(rf"(?i)\b{re.escape(dep)}\b", source):
            analysis.stack.add(stack)
    for dep, (name, kind) in DATASTORE_DEPENDENCIES.items():
        if re.search(rf"(?i)\b{re.escape(dep)}\b", source):
            _datastore(analysis, fnode, path, content_hash, dep, name, kind, 1)

def _dockerfile(analysis, path, content_hash, source):
    analysis.stack.add("Docker")
    for lineno, line in enumerate(source.splitlines(), 1):
        if line.strip().upper().startswith("FROM "):
            image = line.strip().split(None, 1)[1]
            analysis.nodes.append(Node(
                id=f"INFRA-{stable_id(path, 'image', image)}", kind="INFRA_RESOURCE", name=image, path=path,
                properties={"type": "container-base-image"},
                evidence=[evidence(path, content_hash, lineno, note="Docker FROM")],
            ))

def _compose_text(analysis, fnode, path, content_hash, source):
    known = {"postgres": "PostgreSQL", "mysql": "MySQL", "mongo": "MongoDB", "redis": "Redis", "kafka": "Kafka", "rabbitmq": "RabbitMQ"}
    for lineno, line in enumerate(source.splitlines(), 1):
        if "image:" in line.lower():
            image = line.split(":", 1)[1].strip()
            for token, name in known.items():
                if token in image.lower():
                    _datastore(analysis, fnode, path, content_hash, token, name, "DATABASE", lineno)

def _dependency(analysis, fnode, path, content_hash, dep, version, line):
    if dep in KNOWN_STACK:
        analysis.stack.add(KNOWN_STACK[dep])
    external = Node(
        id=f"EXTERNAL-{stable_id(dep)}", kind="EXTERNAL_SYSTEM", name=dep,
        properties={"dependency": True, "version_spec": version},
        evidence=[evidence(path, content_hash, line, note="dependency manifest")],
    )
    analysis.nodes.append(external)
    analysis.edges.append(Edge(
        id=f"EDGE-{stable_id('DEPENDS_ON', fnode.id, external.id)}",
        kind="DEPENDS_ON", source=fnode.id, target=external.id, evidence=external.evidence[:],
    ))
    if dep in DATASTORE_DEPENDENCIES:
        name, kind = DATASTORE_DEPENDENCIES[dep]
        _datastore(analysis, fnode, path, content_hash, dep, name, kind, line)

def _datastore(analysis, fnode, path, content_hash, dep, name, kind, line):
    store = Node(
        id=f"DATABASE-{stable_id(name)}", kind=kind, name=name,
        properties={"detected_via": dep},
        evidence=[evidence(path, content_hash, line, note=f"datastore dependency {dep}")],
    )
    analysis.nodes.append(store)
    analysis.edges.append(Edge(
        id=f"EDGE-{stable_id('CONNECTS_TO', fnode.id, store.id)}",
        kind="CONNECTS_TO", source=fnode.id, target=store.id, evidence=store.evidence[:],
    ))
