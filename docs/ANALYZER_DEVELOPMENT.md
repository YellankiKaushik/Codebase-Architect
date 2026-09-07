# Analyzer Development

Analyzers convert untrusted repository files into deterministic CIG facts.

## Contract

Each analyzer returns `FileAnalysis` with:

- nodes
- edges
- evidence
- stack hints
- warnings

`VERIFIED` facts must have deterministic evidence. Dynamic or unresolved behavior should be `INFERRED` or `UNKNOWN`.

## Adding An Analyzer

1. Add a module under `src/codebase_architect/analyzers/`.
2. Register it in `src/codebase_architect/analyzers/registry.py`.
3. Add fixtures and tests.
4. Document static-analysis limitations.

## Security

Do not execute repository code or shell out using repository-controlled values. Treat malformed encodings, huge files, symlinks, generated code, and malicious filenames as expected input.
