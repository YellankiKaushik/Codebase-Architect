from __future__ import annotations

from ..config import Config, ModelConfig, normalize_provider
from ..errors import ConfigurationError
from .base import LLMProvider, NoLLMProvider
from .providers import OllamaProvider, OpenAICompatibleProvider


def provider_from_config(config: ModelConfig, app_config: Config | None = None) -> LLMProvider:
    provider = normalize_provider(config.provider)
    offline = bool(app_config.security.offline) if app_config is not None else False
    if provider == "none":
        return NoLLMProvider()
    if provider == "ollama":
        if not config.name:
            raise ConfigurationError("Ollama provider requires --model or model.name")
        return OllamaProvider(config, offline=offline)
    if provider == "openai-compatible":
        if not config.name:
            raise ConfigurationError("OpenAI-compatible provider requires --model or model.name")
        return OpenAICompatibleProvider(config, offline=offline)
    raise ConfigurationError(f"Unsupported model provider: {provider}")


def provider_types() -> list[dict[str, str]]:
    return [
        {
            "provider": "none",
            "local": "yes",
            "api_key": "no",
            "notes": "Deterministic scan, graph, AIR, docs, and diagrams without model synthesis.",
        },
        {
            "provider": "ollama",
            "local": "yes",
            "api_key": "no",
            "notes": "Uses Ollama /api/tags and /api/generate. Model tag is user-configured.",
        },
        {
            "provider": "openai-compatible",
            "local": "yes when pointed at loopback",
            "api_key": "optional via model.api_key_env",
            "notes": "Uses /models and /chat/completions for local OpenAI-compatible runtimes.",
        },
    ]
