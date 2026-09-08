# Getting Started

## Install From Source

```bash
git clone https://github.com/YellankiKaushik/Codebase-Architect.git
cd Codebase-Architect
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
codebase-architect doctor
```

For full JavaScript/TypeScript AST support, install with:

```bash
python -m pip install -e ".[javascript]"
```

Without the `javascript` extra, Codebase Architect automatically falls back to structural JS/TS analysis.

On Windows, activate with:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Analyze Without AI

```bash
codebase-architect init .
codebase-architect analyze . --no-llm
codebase-architect validate docs/codebase
```

## Analyze With A Local Model

```bash
codebase-architect analyze . --offline --provider ollama --model <their-local-model-name>
```

Model quality affects semantic explanations. Deterministic extraction still runs independently.

## Inspect Results

Important outputs:

- `docs/codebase/DEEP_TECHNICAL_ARCHITECTURE.md`
- `docs/codebase/evidence/code-intelligence-graph.json`
- `docs/codebase/evidence/architecture.json`
- `docs/codebase/evidence/run-manifest.json`
- `docs/codebase/diagrams/`
