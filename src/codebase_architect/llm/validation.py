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
