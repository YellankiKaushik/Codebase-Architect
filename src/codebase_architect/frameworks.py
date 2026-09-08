from __future__ import annotations

from .analyzers.base import stable_id
from .graph import CodeGraph
from .models import Edge, Node


FRAMEWORKS = {
    "FastAPI", "Flask", "Django", "Express", "Fastify", "NestJS", "Next.js", "React",
    "Prisma", "TypeORM", "Sequelize", "MongoDB", "SQLAlchemy", "Django ORM", "Redis",
    "Docker", "Docker Compose", "GitHub Actions", "PostgreSQL", "MySQL",
}


def detect_frameworks(graph: CodeGraph, stack: set[str]) -> list[dict]:
    detected: dict[str, dict] = {}
    for item in stack:
        name = _normalize_framework(item)
        if name:
            detected.setdefault(name, {"name": name, "evidence_ids": set(), "entrypoints": set(), "confidence": 0.75})
    for node in graph.nodes.values():
        text = " ".join([node.name, str(node.properties.get("dependency", "")), str(node.properties.get("version_spec", ""))])
        name = _normalize_framework(text)
        if not name:
            continue
        current = detected.setdefault(name, {"name": name, "evidence_ids": set(), "entrypoints": set(), "confidence": 0.8})
        current["evidence_ids"].update(ev.id for ev in node.evidence)
        if node.path:
            current["entrypoints"].add(node.path)
    results = []
    for item in detected.values():
        node = Node(
            id=f"FRAMEWORK-{stable_id(item['name'])}", kind="FRAMEWORK", name=item["name"],
            properties={
                "confidence": item["confidence"],
                "entrypoints": sorted(item["entrypoints"]),
                "evidence_ids": sorted(item["evidence_ids"]),
            },
        )
        graph.add_node(node)
        for path in item["entrypoints"]:
            file_node = next((candidate for candidate in graph.nodes_by_kind("FILE") if candidate.path == path), None)
            if file_node:
                graph.add_edge(Edge(
                    id=f"EDGE-{stable_id('DEPENDS_ON', file_node.id, node.id)}",
                    kind="DEPENDS_ON", source=file_node.id, target=node.id,
                    confidence=item["confidence"], evidence=file_node.evidence[:1],
                ))
        results.append({
            "framework": item["name"],
            "confidence": item["confidence"],
            "evidence_ids": sorted(item["evidence_ids"]),
            "entrypoints": sorted(item["entrypoints"]),
        })
    return sorted(results, key=lambda value: value["framework"])


def _normalize_framework(text: str) -> str | None:
    lower = text.lower()
    mapping = {
        "fastapi": "FastAPI",
        "flask": "Flask",
        "django orm": "Django ORM",
        "django": "Django",
        "express": "Express",
        "fastify": "Fastify",
        "nestjs": "NestJS",
        "@nestjs": "NestJS",
        "next.js": "Next.js",
        "next": "Next.js",
        "react": "React",
        "prisma": "Prisma",
        "typeorm": "TypeORM",
        "sequelize": "Sequelize",
        "mongoose": "MongoDB",
        "mongodb": "MongoDB",
        "sqlalchemy": "SQLAlchemy",
        "redis": "Redis",
        "docker compose": "Docker Compose",
        "github actions": "GitHub Actions",
        "postgresql": "PostgreSQL",
        "postgres": "PostgreSQL",
        "mysql": "MySQL",
    }
    for token, name in mapping.items():
        if token in lower:
            return name
    return text if text in FRAMEWORKS else None
