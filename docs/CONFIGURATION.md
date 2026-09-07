# Configuration

Codebase Architect reads `.codebase-architect.toml` from the analyzed repository unless `--config` points somewhere else. CLI flags override matching config fields.

## Schema

```toml
version = 1

[analysis]
detail = "deep"
max_file_bytes = 1000000
exclude = ["node_modules/**", "vendor/**", "dist/**", "build/**", "coverage/**"]

[model]
provider = "none"
name = ""
base_url = "http://127.0.0.1:11434"
timeout_seconds = 120
retry_attempts = 1
# max_context_tokens = 8192
# api_key_env = "LOCAL_MODEL_API_KEY"

[security]
offline = true
persist_model_cache = false

[output]
path = "docs/codebase"
diagrams = ["technical", "dataflow", "c4", "runtime", "visual"]
overwrite = "generated-only"
```

Unknown keys are rejected so misspellings do not silently disable settings.

## Provider Names

Supported provider values:

- `none`
- `ollama`
- `openai-compatible`

Provider aliases such as `openai_compatible` normalize to `openai-compatible`.

## Secrets

Use `api_key_env` for optional provider credentials. Do not put API key values in configuration files.

## Offline Mode

When `security.offline = true`, model endpoints must use `http` or `https`, must not include URL credentials, and must resolve to loopback addresses. Provider HTTP clients bypass system proxies and reject remote redirects.
