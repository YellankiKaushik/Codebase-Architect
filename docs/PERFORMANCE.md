# Performance Methodology

Codebase Architect includes a benchmark command for deterministic repository analysis:

```bash
codebase-architect benchmark . --no-llm --exclude .tmp/** --json
```

The benchmark command runs analysis and reports:

- `duration_seconds`
- `files_per_second`
- `cache_hit_rate`
- `phase_durations`
- `stats.files_discovered`
- `stats.files_analyzed`
- `stats.files_reused`
- `stats.files_failed`
- `stats.graph_nodes`
- `stats.graph_edges`
- `stats.resolver_edges_added`

## Cold/Warm Cache Methodology

Use a cold run when measuring analyzer and resolver cost from a clean cache. Use a warm run when measuring incremental reuse:

```bash
codebase-architect analyze . --no-llm --output .tmp/perf-cold --exclude .tmp/** --json
codebase-architect analyze . --no-llm --output .tmp/perf-warm --exclude .tmp/** --json
codebase-architect benchmark . --no-llm --exclude .tmp/** --json
```

Warm-cache runs should reuse unchanged file analysis and report a higher cache hit rate. Model-backed runs should additionally record `llm_calls`, `llm_failures`, and redaction count in the run manifest.

Do not compare benchmark results without recording repository size, cache state, Python version, operating system, hardware, provider, model name, context budget, and whether the model was already loaded.
