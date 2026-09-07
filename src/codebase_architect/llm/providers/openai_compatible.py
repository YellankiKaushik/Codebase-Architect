from __future__ import annotations

import os

from ...config import ModelConfig
from ...errors import ProviderProtocolError
from ...secret_filter import redact
from ..base import GenerationRequest, GenerationResult, ModelCapabilities, ModelMetadata
from ..http import SafeHttpClient


class OpenAICompatibleProvider:
    def __init__(self, config: ModelConfig, *, offline: bool = False):
        self.config = config
        self.client = SafeHttpClient(
            config.base_url,
            timeout=config.timeout_seconds,
            offline=offline,
            retry_attempts=config.retry_attempts,
        )
        self.metadata = ModelMetadata(
            provider="openai-compatible",
            model=config.name,
            endpoint=config.base_url,
            capabilities=ModelCapabilities(
                max_context_tokens=config.max_context_tokens,
                supports_json=True,
                supports_system_messages=True,
                supports_streaming=True,
                reports_usage=True,
                provider_type="openai-compatible",
            ),
        )

    def health(self) -> tuple[bool, str]:
        try:
            raw = self.client.get_json("/models", headers=self._headers())
            models = raw.get("data", [])
            if self.config.name and isinstance(models, list):
                names = {str(item.get("id", "")) for item in models if isinstance(item, dict)}
                if names and self.config.name not in names:
                    return False, f"OpenAI-compatible endpoint reachable, but model {self.config.name!r} was not listed"
            return True, "OpenAI-compatible endpoint reachable"
        except Exception as exc:
            return False, f"OpenAI-compatible provider unavailable: {exc}"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        safe_system, safe_prompt = redact(request.system), redact(request.prompt)
        payload = {
            "model": self.config.name,
            "messages": [
                {"role": "system", "content": safe_system.text},
                {"role": "user", "content": safe_prompt.text},
            ],
            "temperature": self.config.temperature,
        }
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}
        raw = self.client.post_json("/chat/completions", payload, headers=self._headers())
        try:
            choice = raw["choices"][0]
            text = str(choice["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderProtocolError("OpenAI-compatible response missing choices[0].message.content") from exc
        usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else None
        return GenerationResult(
            text=text[:request.max_output_chars],
            request_id=request.request_id,
            redactions=safe_system.count + safe_prompt.count,
            usage=usage,
        )

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.config.api_key_env:
            value = os.environ.get(self.config.api_key_env)
            if value:
                headers["Authorization"] = f"Bearer {value}"
        return headers
