from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

SCHEMA_VERSION = "1"

class Classification(str, Enum):
    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"

class NodeKind(str, Enum):
    REPOSITORY = "REPOSITORY"
    PACKAGE = "PACKAGE"
    MODULE = "MODULE"
    FILE = "FILE"
    CLASS = "CLASS"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    API_ENDPOINT = "API_ENDPOINT"
    DATABASE = "DATABASE"
    TABLE = "TABLE"
    EVENT = "EVENT"
    QUEUE = "QUEUE"
    JOB = "JOB"
    EXTERNAL_SYSTEM = "EXTERNAL_SYSTEM"
    CONFIGURATION_KEY = "CONFIGURATION_KEY"
    INFRA_RESOURCE = "INFRA_RESOURCE"
    TEST = "TEST"
    WORKFLOW = "WORKFLOW"

class EdgeKind(str, Enum):
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    EXPOSES = "EXPOSES"
    HANDLES = "HANDLES"
    READS = "READS"
    WRITES = "WRITES"
    PUBLISHES = "PUBLISHES"
    CONSUMES = "CONSUMES"
    DEPENDS_ON = "DEPENDS_ON"
    CONFIGURED_BY = "CONFIGURED_BY"
    CONNECTS_TO = "CONNECTS_TO"
    TESTED_BY = "TESTED_BY"
    DEPLOYED_AS = "DEPLOYED_AS"

@dataclass(slots=True)
class Evidence:
    id: str
    path: str
    line_start: int | None = None
    line_end: int | None = None
    symbol: str | None = None
    content_hash: str | None = None
    note: str | None = None
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Evidence":
        return cls(**value)

@dataclass(slots=True)
class Node:
    id: str
    kind: str
    name: str
    path: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    classification: str = Classification.VERIFIED.value
    evidence: list[Evidence] = field(default_factory=list)
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [e.to_dict() for e in self.evidence]
        return data
    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Node":
        raw = dict(value)
        raw["evidence"] = [Evidence.from_dict(e) for e in raw.get("evidence", [])]
        return cls(**raw)

@dataclass(slots=True)
class Edge:
    id: str
    kind: str
    source: str
    target: str
    properties: dict[str, Any] = field(default_factory=dict)
    classification: str = Classification.VERIFIED.value
    confidence: float = 1.0
    evidence: list[Evidence] = field(default_factory=list)
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [e.to_dict() for e in self.evidence]
        return data
    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Edge":
        raw = dict(value)
        raw["evidence"] = [Evidence.from_dict(e) for e in raw.get("evidence", [])]
        return cls(**raw)

@dataclass(slots=True)
class FileRecord:
    path: str
    absolute_path: str
    size_bytes: int
    content_hash: str
    language: str
    generated: bool = False

@dataclass(slots=True)
class FileAnalysis:
    path: str
    content_hash: str
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stack: set[str] = field(default_factory=set)
    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "content_hash": self.content_hash,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "warnings": self.warnings,
            "stack": sorted(self.stack),
        }
    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "FileAnalysis":
        return cls(
            path=value["path"],
            content_hash=value["content_hash"],
            nodes=[Node.from_dict(n) for n in value.get("nodes", [])],
            edges=[Edge.from_dict(e) for e in value.get("edges", [])],
            warnings=list(value.get("warnings", [])),
            stack=set(value.get("stack", [])),
        )

@dataclass(slots=True)
class ArchitectureComponent:
    id: str
    name: str
    paths: list[str]
    responsibility: str
    node_ids: list[str]
    dependencies: list[str] = field(default_factory=list)
    classification: str = Classification.INFERRED.value
    evidence_ids: list[str] = field(default_factory=list)
    summary: str | None = None
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class ArchitectureIR:
    schema_version: str
    repository_name: str
    architecture_style: str
    components: list[ArchitectureComponent]
    external_systems: list[dict[str, Any]]
    datastores: list[dict[str, Any]]
    api_endpoints: list[dict[str, Any]]
    configuration_keys: list[dict[str, Any]]
    workflows: list[dict[str, Any]]
    stack: list[str]
    warnings: list[str] = field(default_factory=list)
    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "repository_name": self.repository_name,
            "architecture_style": self.architecture_style,
            "components": [c.to_dict() for c in self.components],
            "external_systems": self.external_systems,
            "datastores": self.datastores,
            "api_endpoints": self.api_endpoints,
            "configuration_keys": self.configuration_keys,
            "workflows": self.workflows,
            "stack": self.stack,
            "warnings": self.warnings,
        }

@dataclass(slots=True)
class RunStats:
    files_discovered: int = 0
    files_analyzed: int = 0
    files_reused: int = 0
    files_failed: int = 0
    graph_nodes: int = 0
    graph_edges: int = 0
    llm_calls: int = 0
    llm_failures: int = 0
    redactions: int = 0
    warnings: list[str] = field(default_factory=list)
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
