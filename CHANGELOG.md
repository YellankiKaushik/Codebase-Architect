# Changelog

## 0.1.0 - 2026-09-07

- Added Python AST analysis for imports, symbols, routes, calls, and environment references.
- Added Tree-sitter JavaScript/TypeScript AST analysis with structural JS/TS fallback.
- Added cross-file resolver support for local imports, path aliases, and selected symbol relationships.
- Added framework detection for common Python and JavaScript/TypeScript stacks.
- Added Code Intelligence Graph and Architecture IR generation with evidence metadata.
- Added Mermaid technical, dependency, C4, data-flow, runtime, and SVG overview diagrams.
- Added benchmark and deterministic eval commands.
- Added Ollama and OpenAI-compatible provider adapters.
- Hardened offline endpoint validation, redirect handling, secret redaction, and output safety.
- Added structured AI synthesis validation.
- Added Agent Skill installer and packaged skill resource.
- Expanded the test suite to 80 tests with CI across Python 3.11, 3.12, and 3.13.
