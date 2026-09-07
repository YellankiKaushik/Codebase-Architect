from __future__ import annotations

from ...config import ModelConfig
from ...secret_filter import redact
from ..base import GenerationRequest, GenerationResult, ModelCapabilities, ModelMetadata
from ..http import SafeHttpClient


class OllamaProvider:
    def __init__(self, config: ModelConfig, *, offline: bool = False):
        self.config = config
        self.client = SafeHttpClient(
            config.base_url,
            timeout=config.timeout_seconds,
            offline=offline,
            retry_attempts=config.retry_attempts,
        )
        self.metadata = ModelMetadata(
            provider="ollama",
            model=config.name,
            endpoint=config.base_url,
            capabilities=ModelCapabilities(
                max_context_tokens=config.max_context_tokens,
                supports_json=True,
                supports_system_messages=True,
                supports_streaming=True,
                reports_usage=False,
                provider_type="ollama",
            ),
        )

    def health(self) -> tuple[bool, str]:
        try:
            raw = self.client.get_json("/api/tags")
            models = raw.get("models", [])
            if self.config.name and isinstance(models, list):
                names = {str(item.get("name", "")) for item in models if isinstance(item, dict)}
                if names and self.config.name not in names:
                    return False, f"Ollama reachable, but model {self.config.name!r} was not listed"
            return True, "Ollama reachable"
        except Exception as exc:
            return False, f"Ollama unavailable: {exc}"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        safe_system, safe_prompt = redact(request.system), redact(request.prompt)
        payload = {
            "model": self.config.name,
            "system": safe_system.text,
            "prompt": safe_prompt.text,
            "stream": False,
            "format": "json" if request.response_format == "json" else None,
            "options": {"temperature": self.config.temperature},
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        raw = self.client.post_json("/api/generate", payload)
        text = str(raw.get("response", "")).strip()
        return GenerationResult(
            text=text[:request.max_output_chars],
            request_id=request.request_id,
            redactions=safe_system.count + safe_prompt.count,
            raw_metadata={"done": raw.get("done")},
        )
