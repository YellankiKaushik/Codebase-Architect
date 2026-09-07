# Troubleshooting

| Symptom | Check | Resolution |
|---|---|---|
| CLI not found | `codebase-architect doctor` | Install the package into the active Python environment or with `pipx`/`uv tool`. |
| No files analyzed | output manifest stats | Check `analysis.exclude`, `analysis.focus`, and file-size limits. |
| Model unavailable | `codebase-architect models --provider ...` | Start the local runtime and confirm the configured model name. |
| Offline endpoint blocked | error message host | Use a loopback URL such as `http://127.0.0.1:11434`. |
| Existing docs protected | generated overwrite error | Move or rename hand-written docs, or use a clean output directory. |
| Validation fails on secrets | `validation-report.md` | Inspect source/output locally; the report does not include secret values. |
| Diagrams are too large | component count | Use `--focus` or a smaller repository slice. |

## Useful Commands

```bash
codebase-architect doctor --json
codebase-architect providers --json
codebase-architect analyze . --no-llm --json
codebase-architect validate docs/codebase --json
codebase-architect eval --json
```
