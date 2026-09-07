from __future__ import annotations
from collections import defaultdict
from pathlib import Path
from .graph import CodeGraph
from .models import ArchitectureComponent, ArchitectureIR, Classification, SCHEMA_VERSION

def infer_architecture(repository: Path, graph: CodeGraph, stack: set[str], warnings: list[str]) -> ArchitectureIR:
    files = graph.nodes_by_kind("FILE")
    grouped: dict[str, list] = defaultdict(list)
    for node in files:
        path = node.path or node.name
        parts = Path(path).parts
        if not parts: key = "root"
        elif parts[0] in {"src", "app", "lib", "packages", "services", "apps"} and len(parts) > 1:
            key = "/".join(parts[:2])
        else: key = parts[0]
        grouped[key].append(node)
    components: list[ArchitectureComponent] = []
    for key, members in sorted(grouped.items()):
        node_ids = {m.id for m in members}
        member_paths = sorted(m.path for m in members if m.path)
        dependencies, evidence_ids = set(), set()
        for member in members:
            evidence_ids.update(e.id for e in member.evidence)
            for edge_id in graph.outgoing.get(member.id, set()):
                edge = graph.edges[edge_id]
                target = graph.nodes.get(edge.target)
                if target and target.kind in {"MODULE", "EXTERNAL_SYSTEM", "DATABASE"}:
                    dependencies.add(target.name)
        components.append(ArchitectureComponent(
            id=f"CMP-{len(components)+1:03d}", name=key, paths=member_paths,
            responsibility=_responsibility(key, members, graph),
            node_ids=sorted(node_ids), dependencies=sorted(dependencies),
            classification=Classification.INFERRED.value, evidence_ids=sorted(evidence_ids),
        ))
    external_systems = [{
        "id": n.id, "name": n.name, "classification": n.classification,
        "evidence": [e.id for e in n.evidence], "properties": n.properties,
    } for n in graph.nodes_by_kind("EXTERNAL_SYSTEM")]
    datastores = [{
        "id": n.id, "name": n.name, "classification": n.classification,
        "evidence": [e.id for e in n.evidence], "properties": n.properties,
    } for n in graph.nodes_by_kind("DATABASE")]
    endpoints = [{
        "id": n.id, "name": n.name, "path": n.properties.get("path"),
        "method": n.properties.get("method"), "source": n.path,
        "classification": n.classification, "evidence": [e.id for e in n.evidence],
    } for n in graph.nodes_by_kind("API_ENDPOINT")]
    config_keys = [{
        "id": n.id, "name": n.name,
        "sensitive_candidate": bool(n.properties.get("sensitive_candidate")),
        "classification": n.classification, "evidence": [e.id for e in n.evidence],
    } for n in graph.nodes_by_kind("CONFIGURATION_KEY")]
    return ArchitectureIR(
        schema_version=SCHEMA_VERSION, repository_name=repository.name,
        architecture_style=_style(components, stack),
        components=components, external_systems=_dedupe_named(external_systems),
        datastores=_dedupe_named(datastores), api_endpoints=endpoints,
        configuration_keys=_dedupe_named(config_keys),
        workflows=_infer_workflows(graph), stack=sorted(stack), warnings=warnings,
    )

def _responsibility(key: str, members: list, graph: CodeGraph) -> str:
    names = " ".join((m.path or m.name).lower() for m in members)
    endpoints = sum(1 for member in members for edge_id in graph.outgoing.get(member.id, set()) if graph.edges[edge_id].kind == "EXPOSES")
    if endpoints or any(t in names for t in ("api", "route", "controller")):
        return "Handles inbound application/API interfaces and request routing."
    if any(t in names for t in ("db", "data", "repo", "model", "storage", "migration")):
        return "Owns persistence, data-access, or schema-related concerns."
    if any(t in names for t in ("test", "spec")):
        return "Contains automated verification and test support."
    if any(t in names for t in ("infra", "deploy", "docker", ".github")):
        return "Defines build, deployment, automation, or infrastructure behavior."
    if any(t in names for t in ("ui", "web", "frontend", "client", "components")):
        return "Implements user-facing/client-side application behavior."
    return f"Groups implementation located under `{key}`; exact business responsibility requires semantic evidence."

def _style(components: list[ArchitectureComponent], stack: set[str]) -> str:
    service_like = sum(1 for c in components if c.name.startswith(("services/", "apps/", "packages/")))
    if service_like >= 3: return "multi-package / service-oriented repository (inferred)"
    if "Next.js" in stack: return "full-stack web application (inferred)"
    if len(components) <= 8: return "modular application / monolith (inferred)"
    return "multi-module application (inferred)"

def _infer_workflows(graph: CodeGraph) -> list[dict]:
    workflows = []
    for endpoint in graph.nodes_by_kind("API_ENDPOINT"):
        incoming = [graph.edges[eid] for eid in graph.incoming.get(endpoint.id, set())]
        source = graph.nodes.get(incoming[0].source) if incoming else None
        steps = [endpoint.name]
        if source:
            steps.append(source.name)
            for node_id in sorted(graph.neighbors(source.id, depth=1)):
                node = graph.nodes.get(node_id)
                if node and node.id != source.id and node.kind in {"DATABASE", "EXTERNAL_SYSTEM", "EVENT"}:
                    steps.append(node.name)
        workflows.append({
            "id": f"WF-{len(workflows)+1:03d}", "name": f"Request flow for {endpoint.name}",
            "trigger": endpoint.name, "steps": steps,
            "classification": Classification.INFERRED.value,
            "evidence": [e.id for e in endpoint.evidence],
        })
    return workflows

def _dedupe_named(items: list[dict]) -> list[dict]:
    result = {}
    for item in items: result.setdefault(item["name"], item)
    return sorted(result.values(), key=lambda i: i["name"].lower())
