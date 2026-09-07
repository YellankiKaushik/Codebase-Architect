from __future__ import annotations

import ipaddress
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_EXCLUDES = [
    ".git/**", ".codebase-architect/**", ".venv/**", "venv/**",
    "node_modules/**", "vendor/**", "dist/**", "build/**",
    "coverage/**", ".next/**", "target/**", "bin/**", "obj/**",
]

@dataclass(slots=True)
class AnalysisConfig:
    detail: str = "standard"
    max_file_bytes: int = 1_000_000
    exclude: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))
    focus: str | None = None

@dataclass(slots=True)
class ModelConfig:
    provider: str = "none"
    name: str = ""
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: int = 120

@dataclass(slots=True)
class SecurityConfig:
    offline: bool = False
    persist_model_cache: bool = False

@dataclass(slots=True)
class OutputConfig:
    path: str = "docs/codebase"
    diagrams: list[str] = field(default_factory=lambda: ["technical", "dataflow", "c4", "runtime", "visual"])

@dataclass(slots=True)
class Config:
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    @classmethod
    def load(cls, repository: Path, explicit_path: Path | None = None) -> "Config":
        config = cls()
        path = explicit_path or repository / ".codebase-architect.toml"
        if not path.exists():
            return config
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        analysis, model = raw.get("analysis", {}), raw.get("model", {})
        security, output = raw.get("security", {}), raw.get("output", {})
        config.analysis = replace(
            config.analysis,
            detail=str(analysis.get("detail", config.analysis.detail)),
            max_file_bytes=int(analysis.get("max_file_bytes", config.analysis.max_file_bytes)),
            exclude=list(dict.fromkeys(config.analysis.exclude + list(analysis.get("exclude", [])))),
            focus=analysis.get("focus", config.analysis.focus),
        )
        config.model = replace(
            config.model,
            provider=str(model.get("provider", config.model.provider)),
            name=str(model.get("name", config.model.name)),
            base_url=str(model.get("base_url", config.model.base_url)),
            timeout_seconds=int(model.get("timeout_seconds", config.model.timeout_seconds)),
        )
        config.security = replace(
            config.security,
            offline=bool(security.get("offline", config.security.offline)),
            persist_model_cache=bool(security.get("persist_model_cache", config.security.persist_model_cache)),
        )
        config.output = replace(
            config.output,
            path=str(output.get("path", config.output.path)),
            diagrams=list(output.get("diagrams", config.output.diagrams)),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.analysis.detail not in {"quick", "standard", "deep", "exhaustive"}:
            raise ValueError(f"Unsupported detail level: {self.analysis.detail}")
        if self.analysis.max_file_bytes <= 0:
            raise ValueError("analysis.max_file_bytes must be positive")
        if self.security.offline and self.model.provider not in {"none", "ollama"}:
            raise ValueError("offline mode only permits the local 'ollama' provider or no model")
        if self.security.offline and self.model.provider == "ollama":
            _require_loopback(self.model.base_url)

def _require_loopback(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise ValueError("Model base URL must contain a host")
    if host == "localhost":
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise ValueError(f"offline mode requires a loopback model endpoint, got: {host}")
