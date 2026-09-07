from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(slots=True)
class ModelCapabilities:
    max_context_tokens: int | None = None
    supports_json: bool = False
    supports_system_messages: bool = True
    supports_streaming: bool = False
    reports_usage: bool = False
    supports_temperature: bool = True
    provider_type: str = "unknown"


@dataclass(slots=True)
class ModelMetadata:
    provider: str
    model: str
    endpoint: str
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)


@dataclass(slots=True)
class GenerationRequest:
    system: str
    prompt: str
    request_id: str
    response_format: str = "text"
    max_output_chars: int = 16_000


@dataclass(slots=True)
class GenerationResult:
    text: str
    request_id: str
    redactions: int = 0
    usage: dict | None = None
    raw_metadata: dict | None = None


class LLMProvider(Protocol):
    metadata: ModelMetadata

    def health(self) -> tuple[bool, str]: ...

    def generate(self, request: GenerationRequest) -> GenerationResult: ...


class NoLLMProvider:
    metadata = ModelMetadata(provider="none", model="", endpoint="", capabilities=ModelCapabilities(provider_type="none"))

    def health(self) -> tuple[bool, str]:
        return True, "LLM disabled"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        raise RuntimeError("LLM generation is disabled")
