# Codebase Architect

**Codebase Architect** turns a software repository into an evidence-backed engineering handbook plus multiple synchronized architecture views.

It is local-first. Deterministic code analysis runs on your machine. Optional semantic synthesis can use a local Ollama model such as Gemma.

```text
Repository
   ↓
Scanner + deterministic analyzers
   ↓
Code Intelligence Graph (CIG) + evidence
   ↓
Architecture Intermediate Representation (AIR)
   ↓
Optional local LLM synthesis
   ↓
Engineering documentation + architecture diagrams
```

The tool does **not** ask an LLM to read an entire repository and guess the architecture.

## Confidence model

- `VERIFIED` — supported by deterministic repository evidence.
- `INFERRED` — derived by rules or model interpretation.
- `UNKNOWN` — not established by available evidence.

## Current MVP

- recursive scanner with exclusions, binary guards, hashing, and symlink containment;
- incremental content-addressed analysis cache;
- Python AST analyzer;
- JavaScript/TypeScript structural analyzer;
- package/config/Docker/GitHub Actions discovery;
- normalized Code Intelligence Graph;
- file/line evidence references;
- architecture inference and component grouping;
- Ollama provider for Gemma or another local model;
- bounded component-by-component synthesis;
- master engineering document and component docs;
- evidence index + JSON CIG/AIR;
- technical, C4, data-flow, runtime, and SVG visual diagrams;
- generated-output validation and secret scanning;
- `--offline` and `--no-llm`;
- Agent Skill for compatible coding agents;
- standard-library-only runtime core.

## Install from source

```bash
git clone https://github.com/YellankiKaushik/Codebase-Architect.git
cd Codebase-Architect
python -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install -e .
codebase-architect doctor
```

## Analyze with no AI

```bash
codebase-architect analyze /path/to/repository --no-llm
```

## Fully local Gemma

Run Ollama and make a Gemma model available, then:

```bash
codebase-architect analyze . \
  --offline \
  --provider ollama \
  --model gemma4:e4b \
  --detail deep
```

`--offline` rejects non-loopback model endpoints.

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

## Commands

```bash
codebase-architect analyze .
codebase-architect update .
codebase-architect diagrams .
codebase-architect validate docs/codebase
codebase-architect inspect . --kind API_ENDPOINT
codebase-architect doctor
```

Focused analysis:

```bash
codebase-architect analyze . --focus src/payments
```

Select views:

```bash
codebase-architect analyze . --diagrams technical,dataflow,c4,runtime,visual
```

## Configuration

`.codebase-architect.toml`:

```toml
[analysis]
detail = "deep"
max_file_bytes = 1000000
exclude = ["node_modules/**", "dist/**", "vendor/**"]

[model]
provider = "ollama"
name = "gemma4:e4b"
base_url = "http://127.0.0.1:11434"

[security]
offline = true
persist_model_cache = false

[output]
path = "docs/codebase"
diagrams = ["technical", "dataflow", "c4", "runtime", "visual"]
```

CLI flags override repository configuration.

## Agent Skill

The repository includes `.github/skills/codebase-architect/SKILL.md`. The skill tells the coding agent to run the engine rather than independently hallucinate an architecture.

## Security

Analyzed repositories are untrusted input. By default the tool does not execute the analyzed project's code, install its packages, or run build/test scripts. It redacts likely secrets before model prompts and scans generated outputs again.

See [SECURITY.md](SECURITY.md).

## Supported languages

- Python
- JavaScript
- TypeScript

More analyzers are intended to be pluggable.

## Design specification

See [docs/DEEP_TECHNICAL_ARCHITECTURE.md](docs/DEEP_TECHNICAL_ARCHITECTURE.md).

## Status

`0.1.0` is an alpha MVP. Static analysis cannot prove all runtime behavior, particularly reflection, generated code, dynamic imports, metaprogramming, runtime DI, and opaque external systems. Codebase Architect surfaces these limits instead of presenting guesses as facts.
