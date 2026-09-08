# Agent Skill Usage

The Agent Skill lets a compatible coding-agent environment invoke Codebase Architect inside another repository.

## Prerequisites

- Python 3.11+
- Codebase Architect CLI installed
- Optional local model runtime such as Ollama

## Install The CLI

From a local checkout:

```bash
python -m pip install -e .
```

For full JavaScript/TypeScript AST analysis, install from the checkout with:

```bash
python -m pip install -e ".[javascript]"
```

From GitHub, when packaging tools are available:

```bash
pipx install git+https://github.com/YellankiKaushik/Codebase-Architect.git
```

or:

```bash
uv tool install git+https://github.com/YellankiKaushik/Codebase-Architect.git
```

## Install The Skill Into Another Repository

```bash
cd my-project
codebase-architect skill install .
```

Result:

```text
my-project/.github/skills/codebase-architect/SKILL.md
```

The installer refuses to overwrite an existing skill unless `--force` is provided.

## Invocation

Open the target repository in an Agent Skills-compatible coding environment and ask the agent to use Codebase Architect, for example:

```text
Use Codebase Architect to deeply document this repository.
```

The skill instructs the agent to run the deterministic CLI rather than inventing architecture from a prompt.

## Output

Generated docs are written to `docs/codebase/` by default.

## Updating Docs

After source changes:

```bash
codebase-architect update . --no-llm
codebase-architect validate docs/codebase
```

## Removing The Skill

Remove this directory from the target repository:

```text
.github/skills/codebase-architect/
```

## Troubleshooting

Run:

```bash
codebase-architect doctor
codebase-architect providers
```

For private repositories, prefer `--no-llm` or `--offline` with a loopback local model endpoint.
