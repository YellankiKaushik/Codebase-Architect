# Security Policy

Codebase Architect treats repositories, comments, manifests, filenames, configuration, generated text, and model output as untrusted input.

## Supported Versions

`0.1.x` is alpha. Security fixes should target the current main branch until formal releases begin.

## Defaults

- Does not execute analyzed application code.
- Does not install analyzed project packages.
- Does not run analyzed repository scripts.
- Does not construct shell commands from repository values.
- Bounds file sizes and skips likely binary files.
- Does not follow directory symlinks during scanning.
- Skips symlink files that resolve outside the repository.
- Redacts likely secrets before model submission.
- Scans generated outputs for likely secrets.
- Refuses to overwrite non-generated documentation and diagram files.
- Supports `--no-llm`.
- Supports `--offline` with loopback-only provider endpoints.

For sensitive repositories:

```bash
codebase-architect analyze . --no-llm
```

or with a local model:

```bash
codebase-architect analyze . --offline --provider ollama --model <their-local-model-name>
```

## Offline Mode

Offline provider calls must use `http` or `https`, must not embed URL credentials, must resolve to loopback addresses, bypass system HTTP proxies, and reject redirects to remote endpoints.

## Secret Handling

The secret filter detects common credential classes but is not a complete DLP system. It records metadata such as finding class/count and never intentionally stores detected secret values.

## Vulnerability Reports

Do not place real credentials or full exploit details in public issues. Prefer GitHub private vulnerability reporting if enabled. If private reporting is unavailable, contact the maintainer through the repository owner profile and share the minimum detail needed to coordinate disclosure.
