from __future__ import annotations

import ipaddress
import re
import socket
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from urllib.parse import urlparse

from .errors import ConfigurationError, SecurityPolicyError

DEFAULT_EXCLUDES = [
    ".git/**", ".codebase-architect/**", ".venv/**", "venv/**",
    "node_modules/**", "vendor/**", "dist/**", "build/**",
    "coverage/**", ".next/**", "target/**", "bin/**", "obj/**",
]
TOP_LEVEL_KEYS = {"version", "analysis", "model", "security", "output"}
SECTION_KEYS = {
    "analysis": {"detail", "max_file_bytes", "exclude", "focus"},
    "model": {
        "provider", "name", "base_url", "api_key_env", "timeout_seconds",
        "max_context_tokens", "retry_attempts", "temperature",
    },
    "security": {"offline", "persist_model_cache"},
    "output": {"path", "diagrams", "overwrite"},
}
PROVIDER_ALIASES = {
    "": "none",
    "disabled": "none",
    "no-llm": "none",
    "openai_compatible": "openai-compatible",
    "openai compatible": "openai-compatible",
}
LOCAL_PROVIDERS = {"none", "ollama", "openai-compatible"}

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
    api_key_env: str | None = None
    timeout_seconds: int = 120
    max_context_tokens: int | None = None
    retry_attempts: int = 1
    temperature: float = 0.1

@dataclass(slots=True)
class SecurityConfig:
    offline: bool = False
    persist_model_cache: bool = False

@dataclass(slots=True)
class OutputConfig:
    path: str = "docs/codebase"
    diagrams: list[str] = field(default_factory=lambda: ["technical", "dataflow", "c4", "runtime", "visual"])
    overwrite: str = "generated-only"

@dataclass(slots=True)
class Config:
    version: int = 1
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
        _reject_unknown_keys(raw)
        config.version = int(raw.get("version", config.version))
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
            provider=normalize_provider(str(model.get("provider", config.model.provider))),
            name=str(model.get("name", config.model.name)),
            base_url=str(model.get("base_url", config.model.base_url)),
            api_key_env=model.get("api_key_env", config.model.api_key_env),
            timeout_seconds=int(model.get("timeout_seconds", config.model.timeout_seconds)),
            max_context_tokens=(
                int(model["max_context_tokens"]) if model.get("max_context_tokens") is not None else config.model.max_context_tokens
            ),
            retry_attempts=int(model.get("retry_attempts", config.model.retry_attempts)),
            temperature=float(model.get("temperature", config.model.temperature)),
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
            overwrite=str(output.get("overwrite", config.output.overwrite)),
        )
        config.validate()
        return config

    def validate(self) -> None:
        self.model = replace(self.model, provider=normalize_provider(self.model.provider))
        if self.version != 1:
            raise ConfigurationError(f"Unsupported config version: {self.version}")
        if self.analysis.detail not in {"quick", "standard", "deep", "exhaustive"}:
            raise ConfigurationError(f"Unsupported detail level: {self.analysis.detail}")
        if self.analysis.max_file_bytes <= 0:
            raise ConfigurationError("analysis.max_file_bytes must be positive")
        if self.model.provider not in LOCAL_PROVIDERS:
            raise ConfigurationError(f"Unsupported model provider: {self.model.provider}")
        if self.model.timeout_seconds <= 0:
            raise ConfigurationError("model.timeout_seconds must be positive")
        if self.model.retry_attempts < 0 or self.model.retry_attempts > 5:
            raise ConfigurationError("model.retry_attempts must be between 0 and 5")
        if self.model.max_context_tokens is not None and self.model.max_context_tokens < 512:
            raise ConfigurationError("model.max_context_tokens must be at least 512 when set")
        if self.model.api_key_env is not None and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.model.api_key_env):
            raise ConfigurationError("model.api_key_env must be an environment variable name, not a secret value")
        if self.output.overwrite not in {"generated-only", "force"}:
            raise ConfigurationError("output.overwrite must be 'generated-only' or 'force'")
        if self.model.provider != "none":
            validate_endpoint(self.model.base_url, offline=self.security.offline)

def normalize_provider(value: str) -> str:
    normalized = value.strip().lower()
    return PROVIDER_ALIASES.get(normalized, normalized)

def validate_endpoint(url: str, offline: bool = False) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SecurityPolicyError(f"Model endpoint scheme is not supported: {parsed.scheme or '<missing>'}")
    if parsed.username or parsed.password:
        raise SecurityPolicyError("Model endpoint must not embed credentials in the URL")
    if parsed.query or parsed.fragment:
        raise SecurityPolicyError("Model endpoint base URL must not contain query strings or fragments")
    host = parsed.hostname
    if not host:
        raise ConfigurationError("Model base URL must contain a host")
    if offline and not is_loopback_host(host):
        raise SecurityPolicyError(f"offline mode blocked non-loopback model endpoint: {host}")

def is_loopback_host(host: str) -> bool:
    if host.lower() in {"localhost", "localhost."}:
        return _resolves_only_to_loopback(host)
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return _resolves_only_to_loopback(host)

def _resolves_only_to_loopback(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    addresses = {item[4][0] for item in infos}
    if not addresses:
        return False
    for address in addresses:
        try:
            if not ipaddress.ip_address(address).is_loopback:
                return False
        except ValueError:
            return False
    return True

def _reject_unknown_keys(raw: dict) -> None:
    unknown_top = sorted(set(raw) - TOP_LEVEL_KEYS)
    if unknown_top:
        raise ConfigurationError(f"Unknown top-level config key(s): {', '.join(unknown_top)}")
    for section, allowed in SECTION_KEYS.items():
        value = raw.get(section, {})
        if value is None:
            continue
        if not isinstance(value, dict):
            raise ConfigurationError(f"Config section [{section}] must be a table")
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ConfigurationError(f"Unknown config key(s) in [{section}]: {', '.join(unknown)}")
