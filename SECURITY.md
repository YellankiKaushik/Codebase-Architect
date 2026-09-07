# Security Policy

Codebase Architect treats repositories, comments, manifests, filenames, and model output as untrusted input.

## Defaults

- does not execute analyzed application code;
- does not automatically install the analyzed project's packages;
- does not construct `shell=True` commands from repository values;
- bounds file sizes and skips binary files;
- rejects symlinks escaping the repository;
- redacts likely secrets before model submission;
- scans generated outputs for likely secrets;
- validates graph and generated artifacts;
- supports fully local/offline operation.

For sensitive repositories:

```bash
codebase-architect analyze . --offline --provider ollama --model <local-model>
```

or:

```bash
codebase-architect analyze . --no-llm
```

## Vulnerability reports

Do not place real credentials or working exploit details in a public issue. Prefer GitHub private vulnerability reporting if enabled.
