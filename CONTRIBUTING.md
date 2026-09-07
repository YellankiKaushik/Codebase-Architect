# Contributing

The core rule is **facts before prose**.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

## Architecture rules

1. Prefer deterministic extraction to an LLM prompt.
2. Every `VERIFIED` relationship carries evidence.
3. Language logic belongs behind an analyzer.
4. Renderers consume AIR and do not re-infer architecture.
5. Repository contents are untrusted input.
6. Do not execute analyzed project code by default.
7. Public schemas are versioned.
8. Unknown facts stay unknown.

## New analyzers

Add an analyzer under `src/codebase_architect/analyzers/`, register it in `registry.py`, and include tests for nodes, relationships, evidence, confidence, malformed input, and false positives.

## Pull requests

Extraction changes require tests. Security-sensitive changes require adversarial tests.
