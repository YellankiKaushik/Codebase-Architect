# Provider Development

Providers live under `src/codebase_architect/llm/providers/` and are registered in `src/codebase_architect/llm/registry.py`.

## Required Interface

A provider exposes:

- `metadata`
- `health() -> tuple[bool, str]`
- `generate(GenerationRequest) -> GenerationResult`

## Rules

- validate endpoints through shared config/HTTP helpers
- bypass system proxies for local/offline calls
- bound response bodies
- retry only retryable failures
- never put API key values in manifests, docs, logs, or exceptions
- return structured provider errors
- support no-LLM degradation where possible

## Tests

Use local mock HTTP servers. Normal CI must not require Ollama, a GPU, or internet access.
