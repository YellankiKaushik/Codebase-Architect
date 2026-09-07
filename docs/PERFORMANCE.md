# Performance Methodology

Codebase Architect does not yet ship a dedicated benchmark command. Use the run manifest to measure current behavior.

## Suggested Local Check

```bash
codebase-architect analyze . --no-llm --output .tmp/perf-cold --exclude .tmp/** --json
codebase-architect analyze . --no-llm --output .tmp/perf-warm --exclude .tmp/** --json
```

Inspect:

- `duration_seconds`
- `phase_durations`
- `stats.files_discovered`
- `stats.files_analyzed`
- `stats.files_reused`
- `stats.files_failed`
- `stats.graph_nodes`
- `stats.graph_edges`

Warm-cache runs should reuse unchanged file analysis. Model-backed runs should additionally record `llm_calls`, `llm_failures`, and redaction count.

Do not compare model-backed timings without recording provider, model name, context budget, runtime, hardware, and whether the model was already loaded.
