from __future__ import annotations
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol
from .config import ModelConfig
from .secret_filter import redact

@dataclass(slots=True)
class GenerationResult:
    text: str
    redactions: int = 0

class LLMProvider(Protocol):
    def health(self) -> tuple[bool, str]: ...
    def generate(self, system: str, prompt: str) -> GenerationResult: ...

class NoLLMProvider:
    def health(self) -> tuple[bool, str]:
        return True, "LLM disabled"
    def generate(self, system: str, prompt: str) -> GenerationResult:
        raise RuntimeError("LLM generation is disabled")

class OllamaProvider:
    def __init__(self, config: ModelConfig):
        self.config = config
        self.base_url = config.base_url.rstrip("/")
    def health(self) -> tuple[bool, str]:
        try:
            request = urllib.request.Request(self.base_url + "/api/tags", method="GET")
            with urllib.request.urlopen(request, timeout=min(5, self.config.timeout_seconds)) as response:
                return (200 <= response.status < 300, "Ollama reachable" if 200 <= response.status < 300 else f"Ollama returned HTTP {response.status}")
        except (OSError, urllib.error.URLError) as exc:
            return False, f"Ollama unavailable: {exc}"
    def generate(self, system: str, prompt: str) -> GenerationResult:
        safe_system, safe_prompt = redact(system), redact(prompt)
        body = json.dumps({
            "model": self.config.name,
            "system": safe_system.text,
            "prompt": safe_prompt.text,
            "stream": False,
            "options": {"temperature": 0.1},
        }).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + "/api/generate",
            data=body, headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama HTTP {exc.code}: {detail[:500]}") from exc
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Ollama generation failed: {exc}") from exc
        return GenerationResult(str(raw.get("response", "")).strip(), safe_system.count + safe_prompt.count)

def provider_from_config(config: ModelConfig) -> LLMProvider:
    if config.provider in {"", "none"}:
        return NoLLMProvider()
    if config.provider == "ollama":
        if not config.name:
            raise ValueError("Ollama provider requires --model or model.name")
        return OllamaProvider(config)
    raise ValueError(f"Unsupported model provider: {config.provider}")
