# Contributing

The core rule is **facts before prose**.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[javascript]"
python -m unittest discover -s tests -v
codebase-architect eval
```

The lightweight core install is still valid:

```bash
python -m pip install -e .
```

Use the `javascript` extra for normal development and CI-equivalent testing so JavaScript/TypeScript AST tests run against Tree-sitter instead of the structural fallback.

## Architecture Rules

1. Prefer deterministic extraction to LLM prompting.
2. Every `VERIFIED` relationship carries evidence.
3. Language logic belongs behind an analyzer.
4. Renderers consume AIR and do not independently infer architecture.
5. Repository contents are untrusted input.
6. Do not execute analyzed project code by default.
7. Public schemas are versioned.
8. Unknown facts stay unknown.
9. Model output cannot upgrade facts to `VERIFIED`.

## New Analyzers

Add an analyzer under `src/codebase_architect/analyzers/`, register it in `registry.py`, and include tests for nodes, relationships, evidence, confidence, malformed input, and false positives.

See `docs/ANALYZER_DEVELOPMENT.md`.

## New Providers

Providers live under `src/codebase_architect/llm/providers/`. They must validate endpoints, avoid leaking credentials, bound response bodies, classify provider errors, and have mock-server tests.

See `docs/PROVIDER_DEVELOPMENT.md`.

## Pull Requests

Extraction changes require tests. Security-sensitive changes require adversarial tests. Documentation must match implemented CLI flags and configuration.
