# Deep Technical Architecture

Status: implemented-alpha architecture reconciled on 2026-09-07.

## Current Processing Model

```text
Repository
  -> scanner
  -> deterministic analyzers
  -> Code Intelligence Graph (CIG)
  -> graph validation
  -> Architecture Intermediate Representation (AIR)
  -> optional validated AI synthesis
  -> docs + diagrams
  -> output validation
```

The repository remains the source of truth. The model subsystem may summarize bounded CIG/AIR context, but it cannot create verified graph facts.

## Implemented Now

| Area | Status |
|---|---|
| CLI | `doctor`, `init`, `analyze`, `update`, `diagrams`, `validate`, `inspect`, `providers`, `models`, `eval`, `skill install` |
| Scanner | recursive filesystem scan, exclusion patterns, binary detection, size limits, hashing, no followed directory symlinks, escaping symlink file skip |
| Python analyzer | AST imports, classes, functions, methods, decorators, common route decorators, calls, env references |
| JS/TS analyzer | structural imports, CommonJS, exports, classes, functions, route registrations, Next.js route handlers, env references, syntactic calls, simple events |
| Config analyzers | package manifests, requirements, pyproject text, Dockerfile, Compose text, GitHub Actions workflows |
| CIG | typed nodes/edges/evidence, deterministic IDs, JSON persistence |
| AIR | component grouping, stack summary, endpoints, datastores, externals, config keys, inferred workflows |
| Diagrams | Mermaid technical/C4/data-flow/runtime plus static SVG overview |
| Providers | no-LLM, Ollama, OpenAI-compatible local adapter |
| Offline policy | http/https only, no URL userinfo, loopback validation, proxy bypass, remote redirect blocking |
| AI output | JSON component synthesis request, validation of component IDs and evidence IDs, no AI-origin `VERIFIED` upgrade |
| Output safety | generated-file markers, non-generated Markdown/diagram overwrite protection, atomic per-file writes, relative output path containment |
| Validation | graph edge integrity, verified-edge evidence, required output files, generated secret scan |
| Eval | small local no-model evaluation checks |

## Target / Future

| Area | Target |
|---|---|
| Cross-file resolution | resolve local imports/exports to symbols rather than mostly module names |
| JS/TS semantic backend | optional Tree-sitter or TypeScript compiler integration with regex fallback |
| Architecture inference | richer deployment, trust-boundary, queue, worker, and layer recognition |
| Renderers | optional D2/Graphviz renderers with graceful fallback |
| Model evaluation | optional model-backed fixture corpus |
| Structured synthesis cache | persist validated summaries only when enabled, keyed by graph/model/prompt versions |
| Performance | documented benchmark command and larger-repository profiling |

## N/A For Current MVP

| Area | Reason |
|---|---|
| SaaS backend | current product is a local CLI |
| Hosted telemetry | no telemetry leaves the computer by default |
| Runtime tracing | static analysis tool; it does not execute analyzed code by default |
| Compliance certification | generated docs may aid review but do not prove compliance |

## Core Data Model

The CIG uses `Node`, `Edge`, and `Evidence` objects from `src/codebase_architect/models.py`.

Important node kinds include files, modules, classes, functions, methods, API endpoints, databases, external systems, configuration keys, infrastructure resources, tests, events, queues, jobs, and workflows.

Important edge kinds include contains, imports, calls, exposes, reads/writes, publishes/consumes, depends-on, configured-by, connects-to, tested-by, and deployed-as.

Each verified edge must carry evidence. Inferred edges carry confidence and classification.

## AI Harness

The provider subsystem lives under `src/codebase_architect/llm/`.

```text
llm/
  base.py
  context.py
  prompts.py
  registry.py
  validation.py
  http.py
  providers/
    ollama.py
    openai_compatible.py
```

Provider adapters expose metadata, capabilities, health, and generation. HTTP calls bypass system proxies, bound response bodies, validate endpoints, and retry only retryable failures.

Prompt construction separates trusted system instructions from untrusted repository JSON context. Component synthesis expects JSON and validates the returned component ID and evidence IDs before turning it into prose.

## Security Boundaries

Repositories are untrusted input. Codebase Architect does not run project scripts or install project dependencies during analysis. Secrets are redacted before provider prompts and generated outputs are scanned again.

Offline model calls must remain local. With `--offline`, endpoints must resolve to loopback and redirects to remote hosts are blocked.

## Diagram Contract

One AIR feeds multiple views. Renderers must not invent nodes that are absent from AIR, except generic diagram actors such as `Engineer / User` where the diagram clearly labels them as context.

## Known Limitations

Static analysis does not guarantee whole-program behavior. Dynamic imports, reflection, decorators/metaprogramming, runtime DI, generated code, framework magic, and external systems remain partial or unknown unless the repository contains supported evidence.
