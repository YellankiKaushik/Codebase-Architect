# Local Models

Codebase Architect is local-first. Deterministic extraction works without a model. Local models only improve semantic explanations over bounded evidence.

## Provider Matrix

| Runtime | Provider config | Local | API key normally required | Notes |
|---|---|---:|---:|---|
| Ollama | `provider = "ollama"` | Yes | No | Uses `/api/tags` and `/api/generate`; model name is whatever `ollama list` reports locally. |
| LM Studio local server | `provider = "openai-compatible"` | Yes when bound to loopback | Usually no | Uses `/v1/models` and `/v1/chat/completions` when compatible. |
| llama.cpp server | `provider = "openai-compatible"` | Yes when bound to loopback | Usually no | Compatibility depends on server flags/version. |
| vLLM local server | `provider = "openai-compatible"` | Yes when bound to loopback | Configuration-dependent | Use the server's exposed model ID. |
| LocalAI | `provider = "openai-compatible"` | Yes when bound to loopback | Configuration-dependent | Use the OpenAI-compatible endpoint if enabled. |
| Jan or similar local servers | `provider = "openai-compatible"` | Yes when bound to loopback | Configuration-dependent | Only mock-tested through the generic adapter, not runtime-specific. |

Only the Ollama and generic OpenAI-compatible adapters are implemented. Runtime-specific rows above are examples of common runtimes that may fit the generic adapter.

## Ollama Gemma Example

1. Install and start Ollama.
2. Make a Gemma model available using the model name supported by your Ollama version.
3. Check the local name:

```bash
ollama list
```

4. Configure:

```toml
[model]
provider = "ollama"
name = "<their-local-gemma-model-name>"
base_url = "http://127.0.0.1:11434"
timeout_seconds = 120
max_context_tokens = 8192
```

5. Verify:

```bash
codebase-architect doctor --provider ollama --model <their-local-gemma-model-name> --offline
```

6. Analyze:

```bash
codebase-architect analyze . --offline --provider ollama --model <their-local-gemma-model-name>
```

## OpenAI-Compatible Local Server

```toml
[model]
provider = "openai-compatible"
name = "my-local-model"
base_url = "http://127.0.0.1:1234/v1"
api_key_env = "OPTIONAL_LOCAL_API_KEY"
timeout_seconds = 120
```

Local endpoints work without API keys when the server permits. If a runtime requires a token, put the token in the named environment variable.

## Hardware Trade-Offs

Small models are usually faster and need less memory, but semantic explanations can be weaker. Larger models may reason better but need more memory and time. Quantization changes memory, performance, and quality. CPU-only inference can work depending on model/runtime, but may be slow. GPU acceleration depends on the runtime, hardware, drivers, and model format.
