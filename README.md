# Codebase Architect

[![CI](https://github.com/YellankiKaushik/Codebase-Architect/actions/workflows/ci.yml/badge.svg)](https://github.com/YellankiKaushik/Codebase-Architect/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Codebase Architect turns a repository into evidence-backed engineering documentation and synchronized architecture diagrams. It is local-first: deterministic scanners build the Code Intelligence Graph (CIG), architecture inference builds the Architecture Intermediate Representation (AIR), and optional local AI only explains bounded evidence.

```text
Repository
  -> scanner + deterministic analyzers
  -> Code Intelligence Graph + evidence
  -> Architecture Intermediate Representation
  -> optional local AI synthesis
  -> docs/codebase documentation + diagrams
  -> validation report
```

The LLM is not the source of truth. Structural claims come from repository evidence wherever the current analyzers can extract it.

## Status

`0.1.0` is a public alpha-quality local tool. It supports Python, JavaScript, TypeScript, common package/config files, GitHub Actions discovery, Mermaid/SVG diagram source, and no-LLM documentation generation. Static analysis cannot prove all runtime behavior, especially reflection, generated code, dynamic imports, runtime dependency injection, or opaque external systems.

## Features

- deterministic scanner with exclusions, size limits, hashing, binary guards, and symlink containment
- Python AST analyzer
- JavaScript/TypeScript Tree-sitter AST analysis when installed with the `javascript` extra, with structural analysis as a graceful fallback
- package/config/Docker/GitHub Actions discovery
- normalized CIG with evidence IDs
- AIR component grouping and explainable architecture classification
- optional Ollama provider
- optional generic OpenAI-compatible local provider
- offline policy for loopback-only model endpoints
- structured AI synthesis validation
- generated documentation overwrite protection
- validation report and run manifest
- Agent Skill installer for other repositories

## Confidence Model

| Classification | Meaning |
|---|---|
| `VERIFIED` | deterministic repository evidence supports the structural claim |
| `INFERRED` | rule or model interpretation based on evidence but not fully proven |
| `UNKNOWN` | current repository evidence does not establish the fact |

AI output may help summarize or classify, but it cannot upgrade a claim to `VERIFIED`.

## Install

From a local checkout:

```bash
git clone https://github.com/YellankiKaushik/Codebase-Architect.git
cd Codebase-Architect
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e .
codebase-architect doctor
```

Core installs include Python AST support and JavaScript/TypeScript structural fallback without requiring Tree-sitter.

For full JavaScript/TypeScript AST support, install the optional extra:

```bash
python -m pip install -e ".[javascript]"
```

Use the full install when you want professional JavaScript/TypeScript repository analysis. Without the `javascript` extra, Codebase Architect automatically falls back to structural JS/TS analysis.

Source tool installs should work when Python packaging tools are available:

```bash
pipx install git+https://github.com/YellankiKaushik/Codebase-Architect.git
uv tool install git+https://github.com/YellankiKaushik/Codebase-Architect.git
```

## 60-Second Quick Start

```bash
codebase-architect init .
codebase-architect analyze . --no-llm
codebase-architect validate docs/codebase
```

Open `docs/codebase/DEEP_TECHNICAL_ARCHITECTURE.md` and `docs/codebase/diagrams/`.

## Local Gemma Example

Model tags vary by runtime and release. Install/start Ollama, make a Gemma model available, then substitute the exact local model name reported by your runtime:

```bash
ollama list
codebase-architect doctor --provider ollama --model <their-local-gemma-model-name> --offline
codebase-architect analyze . \
  --offline \
  --provider ollama \
  --model <their-local-gemma-model-name>
```

Gemma is an example, not a hard-coded requirement.

## Other Local Models

Use any model your local runtime exposes through an implemented adapter:

```toml
[model]
provider = "openai-compatible"
name = "my-local-model"
base_url = "http://127.0.0.1:1234/v1"
api_key_env = "OPTIONAL_LOCAL_API_KEY"
timeout_seconds = 120
max_context_tokens = 8192
```

See [docs/LOCAL_MODELS.md](docs/LOCAL_MODELS.md).

## CLI

```bash
codebase-architect doctor
codebase-architect init .
codebase-architect analyze . --no-llm
codebase-architect update .
codebase-architect diagrams .
codebase-architect validate docs/codebase
codebase-architect inspect . --kind API_ENDPOINT
codebase-architect providers
codebase-architect models --provider ollama --model <model-name> --offline
codebase-architect eval
codebase-architect skill install .
```

`update` currently reuses the same incremental cache-backed pipeline as `analyze`. `diagrams` runs analysis with LLM disabled and emits diagram artifacts from AIR.

## Output

```text
docs/codebase/
├── README.md
├── DEEP_TECHNICAL_ARCHITECTURE.md
├── components/
├── diagrams/
│   ├── technical.mmd
│   ├── c4-containers.mmd
│   ├── data-flow.mmd
│   ├── runtime.mmd
│   └── visual-overview.svg
├── evidence/
│   ├── evidence-index.md
│   ├── code-intelligence-graph.json
│   ├── architecture.json
│   └── run-manifest.json
└── validation-report.md
```

## Agent Skill

Install the CLI once, then in another repository:

```bash
cd my-project
codebase-architect skill install .
```

This creates:

```text
my-project/.github/skills/codebase-architect/SKILL.md
```

The skill instructs compatible coding agents to invoke the deterministic CLI and write generated docs to `docs/codebase/`. See [docs/AGENT_SKILL_USAGE.md](docs/AGENT_SKILL_USAGE.md).

## Privacy And Security

By default the tool does not execute analyzed project code, install project dependencies, run repository scripts, or send telemetry. `--no-llm` performs deterministic analysis only. `--offline` rejects non-loopback model endpoints and blocks remote redirects in provider HTTP clients.

Repository content is hostile input. Prompts separate trusted instructions from untrusted repository context, likely secrets are redacted before model calls, and generated output is scanned for likely secrets.

See [SECURITY.md](SECURITY.md) and [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md).

## Documentation

- [Getting Started](docs/GETTING_STARTED.md)
- [Configuration](docs/CONFIGURATION.md)
- [Local Models](docs/LOCAL_MODELS.md)
- [Agent Skill Usage](docs/AGENT_SKILL_USAGE.md)
- [Security Model](docs/SECURITY_MODEL.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Provider Development](docs/PROVIDER_DEVELOPMENT.md)
- [Analyzer Development](docs/ANALYZER_DEVELOPMENT.md)
- [Performance Methodology](docs/PERFORMANCE.md)
- [Deep Technical Architecture](docs/DEEP_TECHNICAL_ARCHITECTURE.md)

## Development

```bash
python -m pip install -e ".[javascript]"
python -m unittest discover -s tests -v
codebase-architect eval
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Roadmap

- richer cross-file symbol resolution
- deeper TypeScript semantic/type resolution
- larger fixture corpus and optional model-backed evaluations
- optional D2/Graphviz renderers
- cache policy controls for structured AI synthesis
- broader analyzer ecosystem
