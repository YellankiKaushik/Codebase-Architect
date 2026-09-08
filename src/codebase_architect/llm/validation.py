from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ..graph import CodeGraph


@dataclass(slots=True)
class ComponentSynthesis:
    component_id: str
    purpose: str
    responsibilities: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    runtime_behavior: str = "UNKNOWN"
    risks: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)

    def summary_text(self) -> str:
        parts = [self.purpose.strip() or "UNKNOWN"]
        if self.responsibilities:
            parts.append("Responsibilities: " + "; ".join(self.responsibilities[:5]))
        if self.runtime_behavior and self.runtime_behavior != "UNKNOWN":
            parts.append("Runtime behavior: " + self.runtime_behavior)
        if self.unknowns:
            parts.append("Unknowns: " + "; ".join(self.unknowns[:4]))
        return "\n\n".join(parts)


@dataclass(slots=True)
class WorkflowSynthesis:
    workflow_id: str
    name: str
    trigger: str
    steps: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SystemSummary:
    repository_name: str
    purpose: str
    architecture_style: str
    major_components: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RiskCandidate:
    title: str
    severity: str
    rationale: str
    mitigation: str = "UNKNOWN"
    evidence_ids: list[str] = field(default_factory=list)


def parse_component_synthesis(text: str, component, graph: CodeGraph) -> tuple[ComponentSynthesis | None, list[str]]:
    warnings: list[str] = []
    try:
        raw = json.loads(_extract_json_object(text))
    except (json.JSONDecodeError, ValueError) as exc:
        return None, [f"structured synthesis rejected: invalid JSON: {exc}"]
    if not isinstance(raw, dict):
        return None, ["structured synthesis rejected: response is not an object"]
    required = {"component_id", "purpose", "responsibilities", "dependencies", "runtime_behavior", "risks", "unknowns", "evidence_ids"}
    missing = sorted(required - set(raw))
    if missing:
        return None, [f"structured synthesis rejected: missing field(s): {', '.join(missing)}"]
    if raw.get("component_id") != component.id:
        return None, [f"structured synthesis rejected: component_id {raw.get('component_id')!r} does not match {component.id!r}"]
    evidence_ids = _list_of_str(raw.get("evidence_ids"))
    known_evidence = {ev.id for node in graph.nodes.values() for ev in node.evidence}
    known_evidence.update(ev.id for edge in graph.edges.values() for ev in edge.evidence)
    invalid_evidence = [ev for ev in evidence_ids if ev not in known_evidence]
    if invalid_evidence:
        warnings.append(f"model cited unknown evidence ID(s): {', '.join(invalid_evidence[:10])}")
        evidence_ids = [ev for ev in evidence_ids if ev in known_evidence]
    if "VERIFIED" in json.dumps(raw).upper():
        warnings.append("model attempted to assign VERIFIED status; status ignored")
    return ComponentSynthesis(
        component_id=component.id,
        purpose=_bounded_str(raw.get("purpose"), 1200),
        responsibilities=_list_of_str(raw.get("responsibilities"), limit=8),
        dependencies=_list_of_str(raw.get("dependencies"), limit=20),
        runtime_behavior=_bounded_str(raw.get("runtime_behavior"), 1200),
        risks=_list_of_str(raw.get("risks"), limit=8),
        unknowns=_list_of_str(raw.get("unknowns"), limit=8),
        evidence_ids=evidence_ids[:100],
    ), warnings


def parse_workflow_synthesis(text: str, workflow: dict, graph: CodeGraph) -> tuple[WorkflowSynthesis | None, list[str]]:
    raw, warnings = _parse_object(text)
    if raw is None:
        return None, warnings
    required = {"workflow_id", "name", "trigger", "steps", "risks", "unknowns", "evidence_ids"}
    missing = sorted(required - set(raw))
    if missing:
        return None, [f"structured workflow rejected: missing field(s): {', '.join(missing)}"]
    if raw.get("workflow_id") != workflow.get("id"):
        return None, [f"structured workflow rejected: workflow_id {raw.get('workflow_id')!r} does not match {workflow.get('id')!r}"]
    evidence_ids, evidence_warnings = _validated_evidence_ids(raw.get("evidence_ids"), graph)
    warnings.extend(evidence_warnings)
    _warn_verified(raw, warnings)
    return WorkflowSynthesis(
        workflow_id=_bounded_str(raw.get("workflow_id"), 80),
        name=_bounded_str(raw.get("name"), 200),
        trigger=_bounded_str(raw.get("trigger"), 200),
        steps=_list_of_str(raw.get("steps"), limit=20),
        risks=_list_of_str(raw.get("risks"), limit=8),
        unknowns=_list_of_str(raw.get("unknowns"), limit=8),
        evidence_ids=evidence_ids,
    ), warnings


def parse_system_summary(text: str, repository_name: str, graph: CodeGraph) -> tuple[SystemSummary | None, list[str]]:
    raw, warnings = _parse_object(text)
    if raw is None:
        return None, warnings
    required = {"repository_name", "purpose", "architecture_style", "major_components", "risks", "unknowns", "evidence_ids"}
    missing = sorted(required - set(raw))
    if missing:
        return None, [f"structured system summary rejected: missing field(s): {', '.join(missing)}"]
    if raw.get("repository_name") != repository_name:
        return None, [f"structured system summary rejected: repository_name {raw.get('repository_name')!r} does not match {repository_name!r}"]
    evidence_ids, evidence_warnings = _validated_evidence_ids(raw.get("evidence_ids"), graph)
    warnings.extend(evidence_warnings)
    _warn_verified(raw, warnings)
    return SystemSummary(
        repository_name=repository_name,
        purpose=_bounded_str(raw.get("purpose"), 1200),
        architecture_style=_bounded_str(raw.get("architecture_style"), 300),
        major_components=_list_of_str(raw.get("major_components"), limit=20),
        risks=_list_of_str(raw.get("risks"), limit=12),
        unknowns=_list_of_str(raw.get("unknowns"), limit=12),
        evidence_ids=evidence_ids,
    ), warnings


def parse_risk_candidate(text: str, graph: CodeGraph) -> tuple[RiskCandidate | None, list[str]]:
    raw, warnings = _parse_object(text)
    if raw is None:
        return None, warnings
    required = {"title", "severity", "rationale", "mitigation", "evidence_ids"}
    missing = sorted(required - set(raw))
    if missing:
        return None, [f"structured risk rejected: missing field(s): {', '.join(missing)}"]
    severity = str(raw.get("severity", "")).upper()
    if severity not in {"LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"}:
        return None, [f"structured risk rejected: unsupported severity {raw.get('severity')!r}"]
    evidence_ids, evidence_warnings = _validated_evidence_ids(raw.get("evidence_ids"), graph)
    warnings.extend(evidence_warnings)
    _warn_verified(raw, warnings)
    return RiskCandidate(
        title=_bounded_str(raw.get("title"), 200),
        severity=severity,
        rationale=_bounded_str(raw.get("rationale"), 1200),
        mitigation=_bounded_str(raw.get("mitigation"), 1200),
        evidence_ids=evidence_ids,
    ), warnings


def parse_or_repair_component_synthesis(text: str, component, graph: CodeGraph, repair) -> tuple[ComponentSynthesis | None, list[str]]:
    synthesis, warnings = parse_component_synthesis(text, component, graph)
    if synthesis is not None:
        return synthesis, warnings
    repaired = repair(warnings)
    repaired_synthesis, repaired_warnings = parse_component_synthesis(repaired, component, graph)
    return repaired_synthesis, warnings + [f"repair attempt: {warning}" for warning in repaired_warnings]


def _parse_object(text: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        raw = json.loads(_extract_json_object(text))
    except (json.JSONDecodeError, ValueError) as exc:
        return None, [f"structured response rejected: invalid JSON: {exc}"]
    if not isinstance(raw, dict):
        return None, ["structured response rejected: response is not an object"]
    return raw, []


def _validated_evidence_ids(value: Any, graph: CodeGraph) -> tuple[list[str], list[str]]:
    evidence_ids = _list_of_str(value)
    known_evidence = {ev.id for node in graph.nodes.values() for ev in node.evidence}
    known_evidence.update(ev.id for edge in graph.edges.values() for ev in edge.evidence)
    invalid_evidence = [ev for ev in evidence_ids if ev not in known_evidence]
    warnings: list[str] = []
    if invalid_evidence:
        warnings.append(f"model cited unknown evidence ID(s): {', '.join(invalid_evidence[:10])}")
    return [ev for ev in evidence_ids if ev in known_evidence][:100], warnings


def _warn_verified(raw: dict[str, Any], warnings: list[str]) -> None:
    if "VERIFIED" in json.dumps(raw).upper():
        warnings.append("model attempted to assign VERIFIED status; status ignored")


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found")
    return stripped[start:end + 1]


def _bounded_str(value: Any, max_chars: int = 1000) -> str:
    if not isinstance(value, str):
        return "UNKNOWN"
    return value.strip()[:max_chars] or "UNKNOWN"


def _list_of_str(value: Any, limit: int = 50) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:500] for item in value[:limit] if str(item).strip()]
