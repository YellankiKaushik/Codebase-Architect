# Security Model

## Trust Boundaries

Analyzed repositories are hostile input. Source code, comments, Markdown, filenames, manifests, config values, and model output are data, not instructions.

## Default Behavior

Codebase Architect does not execute analyzed project code, install packages, run repository scripts, or send telemetry by default.

## Model Calls

`--no-llm` disables model synthesis. When a model is used, prompts separate trusted instructions from untrusted repository JSON context. Likely secrets are redacted before prompts are sent.

## Offline Policy

With `--offline`, model endpoint URLs:

- must use `http` or `https`
- must not embed credentials
- must resolve to loopback addresses
- must not redirect to remote hosts
- are called with system HTTP proxies disabled

## Secret Handling

The filter detects common classes such as GitHub tokens, OpenAI-style keys, AWS access keys, bearer tokens, JWT-like tokens, private-key headers, database URLs, connection strings with passwords, and named secret assignments. It records counts/classes, not secret values.

Regex detection is not a complete DLP system. Generated docs are scanned again and validation fails on likely secrets.

## Filesystem Safety

Relative output paths must remain inside the analyzed repository. Generated Markdown and diagram files include markers and non-generated files are not overwritten unless future force behavior explicitly permits it.

## Known Assumptions

The operating system enforces filesystem permissions. Static analysis can miss dynamic behavior. Local model runtimes are trusted to run on the user's machine and enforce their own API security.
