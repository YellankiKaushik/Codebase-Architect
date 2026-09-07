from __future__ import annotations
import json
from pathlib import Path
from .file_safety import GENERATED_MARKER, write_generated
from .graph import CodeGraph
from .models import ArchitectureIR, RunStats

def write_documentation(repository: Path, output: Path, air: ArchitectureIR, graph: CodeGraph, stats: RunStats, commit: str | None, *, force: bool = False) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    (output/"components").mkdir(exist_ok=True)
    evidence_dir=output/"evidence"; evidence_dir.mkdir(exist_ok=True)
    created=[
        _write_guarded(output/"README.md", _index(air), force=force),
        _write_guarded(output/"DEEP_TECHNICAL_ARCHITECTURE.md", _master(repository,air,graph,stats,commit), force=force),
    ]
    for component in air.components:
        created.append(_write_guarded(output/"components"/f"{_slug(component.name)}.md", _component_doc(component), force=force))
    created.append(_write_guarded(evidence_dir/"evidence-index.md", _evidence_index(graph), force=force))
    graph_path=evidence_dir/"code-intelligence-graph.json"; graph_path.write_text(json.dumps(graph.to_dict(),indent=2),encoding="utf-8");created.append(graph_path)
    air_path=evidence_dir/"architecture.json";air_path.write_text(json.dumps(air.to_dict(),indent=2),encoding="utf-8");created.append(air_path)
    return created

def _index(air: ArchitectureIR) -> str:
    return f"""{GENERATED_MARKER}
# {air.repository_name} — Codebase Architecture

Generated from repository evidence.

- [Deep Technical Architecture](DEEP_TECHNICAL_ARCHITECTURE.md)
- [Evidence index](evidence/evidence-index.md)
- [Architecture JSON](evidence/architecture.json)
- [Code Intelligence Graph](evidence/code-intelligence-graph.json)
- [Components](components/)
- [Diagrams](diagrams/)

**Architecture classification:** {air.architecture_style}

`VERIFIED` = deterministic evidence; `INFERRED` = interpretation; `UNKNOWN` = repository did not prove the fact.
"""

def _master(repository: Path, air: ArchitectureIR, graph: CodeGraph, stats: RunStats, commit: str|None) -> str:
    components="\n".join(f"- **{c.name}** — {c.summary or c.responsibility} `[classification: {c.classification}]`" for c in air.components) or "- UNKNOWN"
    stack="\n".join(f"- {x}" for x in air.stack) or "- UNKNOWN"
    endpoints="\n".join(f"- `{e['name']}` — source `{e.get('source')}` — `{e['classification']}`" for e in air.api_endpoints) or "- N/A/UNKNOWN — no statically detected HTTP endpoints."
    datastores="\n".join(f"- **{d['name']}** — `{d['classification']}`" for d in air.datastores) or "- N/A/UNKNOWN — no datastore deterministically detected."
    externals="\n".join(f"- **{d['name']}** — `{d['classification']}`" for d in air.external_systems[:100]) or "- N/A/UNKNOWN"
    configs="\n".join(f"- `{c['name']}`{' — sensitive-name candidate' if c.get('sensitive_candidate') else ''}" for c in air.configuration_keys) or "- UNKNOWN/N/A"
    workflows="\n".join(f"- **{w['name']}**: {' → '.join(w.get('steps',[]))} (`{w['classification']}`)" for w in air.workflows) or "- UNKNOWN — no request workflow could be constructed."
    warnings="\n".join(f"- {w}" for w in air.warnings+stats.warnings) or "- None recorded."
    return f"""{GENERATED_MARKER}
# Deep Technical Architecture & Engineering Documentation

> **System:** {air.repository_name}  
> **Analyzed repository:** `{repository}`  
> **Git commit:** `{commit or 'UNKNOWN — Git revision unavailable'}`  
> **Architecture style:** {air.architecture_style}  
> **Generated from repository evidence:** yes  
> **Status:** Automated draft requiring engineering review

# 1. Executive Technical Overview

`{air.repository_name}` is analyzed as **{air.architecture_style}**.

The structural inventory contains **{len(graph.nodes)} graph nodes** and **{len(graph.edges)} relationships** across **{stats.files_discovered} discovered files**. **{stats.files_reused}** file analyses were reused and **{stats.files_analyzed}** were newly analyzed.

No unproven security, performance, ownership, reliability, deployment, or compliance claim is filled in merely to make the document look complete.

## Technology Stack

{stack}

# 2. Problem / System Purpose

The precise business purpose must be supported by repository semantics or human confirmation. Component-level explanations below are evidence-constrained. If the code does not establish the business objective, it remains UNKNOWN.

# 3. Scope and System Boundary

**Inside boundary:** implementation, configuration, tests, schemas, workflow files, and infrastructure artifacts present in this repository.

**Outside boundary:** referenced packages, services, providers, databases, and systems implemented or operated elsewhere.

# 4. Repository Structure

```text
{_repository_tree(repository)}
```

# 5. High-Level Architecture

**Detected/inferred style:** {air.architecture_style}

The architecture is derived from file containment, imports, calls, routes, configuration references, dependencies, datastores, events, and supported infrastructure artifacts.

# 6. Significant Components

{components}

# 7. Runtime Architecture and Critical Flows

{workflows}

# 8. API and Interface Architecture

{endpoints}

# 9. Event and Messaging Architecture

Detected event nodes: **{len(graph.nodes_by_kind("EVENT"))}**.

Delivery guarantees, ordering, broker retention, replay, and DLQ behavior remain UNKNOWN unless directly present in supported repository evidence.

# 10. Data Architecture

{datastores}

Transaction isolation, indexes, ownership, retention, backup policy, RPO, and RTO remain UNKNOWN unless corresponding evidence exists.

# 11. External Dependencies and Integrations

{externals}

Dependency presence proves a package/system reference. It does not prove production availability, ownership, SLA, or correct runtime configuration.

# 12. Configuration Architecture

{configs}

Secret values are intentionally excluded.

# 13. Security Architecture

## Discoverable Surface

- HTTP/API routes are listed where statically detected.
- sensitive-looking configuration **names** are flagged without exposing values.
- dependency manifests appear in the evidence graph.

## UNKNOWN Unless Proven

Authentication strength, authorization completeness, tenant isolation, encryption policy, MFA, audit retention, vulnerability-management SLA, and regulatory compliance.

# 14. Privacy and Data Protection

UNKNOWN unless data schemas, policies, or code establish personal-data handling. The generator does not infer compliance from framework/package names.

# 15. Infrastructure and Deployment

Detected infrastructure-resource nodes: **{len(graph.nodes_by_kind("INFRA_RESOURCE"))}**.

Cloud accounts, VPCs, replicas, autoscaling, regions, network policies, certificate management, and deployment rollout strategy remain UNKNOWN unless the repository contains supported IaC/deployment evidence.

# 16. Scalability and Performance

No latency, throughput, capacity, scale, or cost number is invented. P50/P95/P99 latency, tested RPS, concurrency, saturation, and cost require benchmark/runtime evidence.

# 17. Reliability and Resilience

Availability, retry/timeout policy, circuit breakers, load shedding, HA, graceful degradation, backup/restore, RPO/RTO, and disaster recovery must be proven from source/configuration/runbooks or remain UNKNOWN.

# 18. Observability

Logging, metrics, tracing, health checks, dashboards, alerts, and SLOs must be validated from code/configuration. Dependency presence alone is insufficient.

# 19. Testing and Quality Engineering

Detected test nodes: **{len(graph.nodes_by_kind("TEST"))}**.

Coverage percentages and environment fidelity remain UNKNOWN without test reports/configuration.

# 20. CI/CD and Release Engineering

Workflow files are modeled as infrastructure resources. Their existence does not prove that a deployment succeeded or that production controls are enforced.

# 21. Operations and Support

Operational owner, on-call coverage, incident process, runbooks, escalation, and vendor contacts remain UNKNOWN unless present in repository documentation/configuration.

# 22. Risks and Static-Analysis Limitations

- reflection and runtime dependency injection can hide relationships;
- dynamic imports and metaprogramming reduce call-graph precision;
- JavaScript/TypeScript call edges are syntactic and lower-confidence;
- generated code may be excluded;
- external systems are opaque beyond repository evidence;
- model-generated prose is subordinate to CIG/AIR evidence;
- missing evidence does not prove a control/system does not exist outside this repository.

# 23. Analysis Warnings

{warnings}

# 24. Evidence and Traceability

See [`evidence/evidence-index.md`](evidence/evidence-index.md).

Machine-readable sources:

- [`evidence/code-intelligence-graph.json`](evidence/code-intelligence-graph.json)
- [`evidence/architecture.json`](evidence/architecture.json)

# 25. Diagram Index

- [`diagrams/technical.mmd`](diagrams/technical.mmd)
- [`diagrams/c4-containers.mmd`](diagrams/c4-containers.mmd)
- [`diagrams/data-flow.mmd`](diagrams/data-flow.mmd)
- [`diagrams/runtime.mmd`](diagrams/runtime.mmd)
- [`diagrams/visual-overview.svg`](diagrams/visual-overview.svg)

# 26. Confidence Model

| Classification | Meaning |
|---|---|
| `VERIFIED` | deterministic repository evidence supports the structural claim |
| `INFERRED` | rule/model interpretation based on evidence but not fully proven |
| `UNKNOWN` | current repository evidence does not establish the fact |

# 27. Required Human Review Before Approval

Verify system purpose, component boundaries, runtime flows, auth/authz, data ownership, deployment topology, failure handling, observability, measured capacity, recovery procedures, and operational ownership.
"""

def _component_doc(c) -> str:
    paths="\n".join(f"- `{p}`" for p in c.paths) or "- UNKNOWN"
    deps="\n".join(f"- {d}" for d in c.dependencies) or "- None statically detected."
    evidence="\n".join(f"- `{e}`" for e in c.evidence_ids[:100]) or "- UNKNOWN"
    return f"""{GENERATED_MARKER}
# Component: {c.name}

**ID:** `{c.id}`  
**Classification:** `{c.classification}`

## What is it?
{c.summary or c.responsibility}

## Why does it exist?
{c.summary or "UNKNOWN — exact business purpose requires semantic or human evidence."}

## Responsibility
{c.responsibility}

## Paths
{paths}

## Dependencies
{deps}

## Inputs / Outputs / Runtime
Inspect the CIG for imports, calls, routes, events, configuration, and datastore relationships. Exact runtime ordering is UNKNOWN unless represented by a workflow.

## Security
UNKNOWN unless source/configuration proves specific controls. Secret values are excluded.

## Concurrency / Idempotency / Failure / Recovery
UNKNOWN unless directly evidenced.

## Performance / Capacity
UNKNOWN — no benchmark is fabricated.

## Testing / Deployment / Rollback
Inspect test and infrastructure evidence. Unproven behavior remains UNKNOWN.

## Evidence IDs
{evidence}
"""

def _evidence_index(graph: CodeGraph) -> str:
    rows=[];seen=set()
    for node in sorted(graph.nodes.values(), key=lambda n:(n.path or "",n.kind,n.name)):
        for ev in node.evidence:
            if ev.id in seen: continue
            seen.add(ev.id);loc=ev.path+(f":{ev.line_start}" if ev.line_start else "")
            rows.append(f"| `{ev.id}` | `{node.kind}` | `{node.name}` | `{loc}` | {ev.note or ''} |")
    for edge in sorted(graph.edges.values(), key=lambda e:e.id):
        for ev in edge.evidence:
            if ev.id in seen: continue
            seen.add(ev.id);loc=ev.path+(f":{ev.line_start}" if ev.line_start else "")
            rows.append(f"| `{ev.id}` | edge `{edge.kind}` | `{edge.source}` → `{edge.target}` | `{loc}` | {ev.note or ''} |")
    table="\n".join(rows) or "| — | — | — | — | No evidence emitted |"
    return f"""{GENERATED_MARKER}
# Evidence Index

| Evidence ID | Subject | Name / Relationship | Location | Note |
|---|---|---|---|---|
{table}
"""

def _repository_tree(repository: Path, max_entries:int=220)->str:
    lines=[repository.name+"/"];count=0
    for path in sorted(repository.rglob("*")):
        try: rel=path.relative_to(repository)
        except ValueError: continue
        if any(part in {".git",".codebase-architect",".venv","node_modules"} for part in rel.parts): continue
        if count>=max_entries: lines.append("  …");break
        lines.append(f'{"  "*max(1,len(rel.parts))}{rel.name}{"/" if path.is_dir() else ""}');count+=1
    return "\n".join(lines)

def _slug(value:str)->str:
    result="".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    while "--" in result: result=result.replace("--","-")
    return result.strip("-") or "component"

def _write_guarded(path:Path,content:str, *, force: bool = False)->Path:
    return write_generated(path, content, force=force)
