# 1. Executive Summary

Codebase Architect was hardened from a compact alpha MVP into a more professional local-first alpha suitable for maintainer review. The core architecture was preserved: scanner/analyzers -> CIG/evidence -> AIR -> optional AI synthesis -> docs/diagrams -> validation.

Major changes include a provider-independent `llm/` subsystem, Ollama and OpenAI-compatible local adapters, stricter offline endpoint policy, structured AI synthesis validation, broader secret detection, generated-output overwrite protection, expanded CLI commands, Agent Skill installation, packaging metadata, CI gates, and user/contributor documentation.

I do not consider this ready for a public beta claim yet. It is ready for review as a serious alpha-hardening pass.

# 2. Initial Audit Findings

| ID | Severity | Area | Problem | Resolution |
|---|---|---|---|---|
| AUD-001 | P1 | Offline networking | Offline mode only allowed Ollama and trusted `localhost` without robust endpoint/redirect/proxy handling. | Added shared endpoint validation, loopback DNS/IP checks, URL credential/query rejection, proxy bypass, and remote redirect blocking. |
| AUD-002 | P1 | AI harness | Single `llm.py` mixed provider protocol, Ollama implementation, errors, and redaction. | Replaced with `src/codebase_architect/llm/` package and provider registry. |
| AUD-003 | P1 | Provider support | No OpenAI-compatible local provider. | Added `/models` + `/chat/completions` adapter with optional `api_key_env`. |
| AUD-004 | P1 | Structured output | AI synthesis accepted free-form prose directly. | Added JSON synthesis prompt and validator for component/evidence IDs. |
| AUD-005 | P1 | Secret handling | Regex coverage was narrow and errors could include unredacted provider response snippets. | Added common secret classes and redacted provider HTTP error bodies. |
| AUD-006 | P1 | Generated output | Diagram files were overwritten without generated-file guard. | Added generated markers and guarded atomic writes. |
| AUD-007 | P1 | Config quality | Unknown config keys were silently ignored and provider config was too small. | Added versioned schema, unknown-key rejection, provider normalization, timeout/retry/context/API-key-env fields. |
| AUD-008 | P2 | CLI UX | Missing real `init`, provider listing, model health, eval, and skill install commands. | Added implemented CLI commands. |
| AUD-009 | P2 | Agent Skill install | Skill existed only inside this repo and was not package-shipped. | Added packaged skill resource and `codebase-architect skill install`. |
| AUD-010 | P2 | JS/TS analyzer | Regex analyzer missed common Next.js and env-access patterns. | Added Next route handler, bracket env, and CommonJS export detection. |
| AUD-011 | P2 | CI/package | CI lacked package build/wheel smoke/eval gates. | Expanded workflow. |
| AUD-012 | P2 | Docs | README and architecture doc mixed implemented behavior with target/future claims. | Rewrote README and reconciled architecture doc with implemented/future/N/A distinctions. |
| AUD-013 | P3 | Contributor experience | Missing changelog, templates, and detailed provider/analyzer docs. | Added supporting docs/templates. |

# 3. Files Changed

| Path | Change | Why |
|---|---|---|
| `.codebase-architect.toml.example` | Modified | Add config version, provider-neutral default, retry/context/API-key-env/output overwrite fields. |
| `.github/skills/codebase-architect/SKILL.md` | Modified | Remove hard-coded Gemma tag from skill example. |
| `.github/workflows/ci.yml` | Modified | Add eval, provider, package build, and wheel install smoke gates. |
| `.gitignore` | Modified | Ignore `.tmp/` verification artifacts. |
| `.github/ISSUE_TEMPLATE/bug_report.md` | Added | Open-source issue workflow. |
| `.github/ISSUE_TEMPLATE/security_note.md` | Added | Public security-report warning. |
| `.github/pull_request_template.md` | Added | Contributor verification/security checklist. |
| `CHANGELOG.md` | Added | Release/change history. |
| `CODE_OF_CONDUCT.md` | Added | Lightweight community norms. |
| `CONTRIBUTING.md` | Modified | Updated contributor/provider/analyzer guidance. |
| `README.md` | Modified | Professional alpha README matching implemented behavior. |
| `SECURITY.md` | Modified | Expanded current security policy. |
| `docs/DEEP_TECHNICAL_ARCHITECTURE.md` | Modified | Replaced stale target-only draft with current-vs-target architecture doc. |
| `docs/GETTING_STARTED.md` | Added | Installation and first-run workflow. |
| `docs/LOCAL_MODELS.md` | Added | Ollama/OpenAI-compatible local model guidance and Gemma workflow. |
| `docs/AGENT_SKILL_USAGE.md` | Added | Skill installation/use in another repository. |
| `docs/CONFIGURATION.md` | Added | Config schema and precedence. |
| `docs/SECURITY_MODEL.md` | Added | Threat model and safety behavior. |
| `docs/TROUBLESHOOTING.md` | Added | User diagnostics. |
| `docs/PROVIDER_DEVELOPMENT.md` | Added | Provider extension rules. |
| `docs/ANALYZER_DEVELOPMENT.md` | Added | Analyzer extension rules. |
| `docs/PERFORMANCE.md` | Added | Documented benchmark methodology using run manifests. |
| `pyproject.toml` | Modified | Add SPDX license, classifiers, package data, URLs, dev dependency group. |
| `src/codebase_architect/errors.py` | Added | Coherent error hierarchy. |
| `src/codebase_architect/file_safety.py` | Added | Output-path and generated-write safety helpers. |
| `src/codebase_architect/eval.py` | Added | Local deterministic evaluation harness. |
| `src/codebase_architect/llm.py` | Deleted | Replaced by provider package. |
| `src/codebase_architect/llm/__init__.py` | Added | Public LLM exports. |
| `src/codebase_architect/llm/base.py` | Added | Provider protocol, generation request/result, metadata/capabilities. |
| `src/codebase_architect/llm/context.py` | Added | Conservative context estimator and budget helpers. |
| `src/codebase_architect/llm/http.py` | Added | Safe HTTP client with proxy bypass, bounded bodies, retry, redirect policy. |
| `src/codebase_architect/llm/prompts.py` | Added | Trusted prompt template and untrusted-context framing. |
| `src/codebase_architect/llm/registry.py` | Added | Provider registry and provider listing. |
| `src/codebase_architect/llm/validation.py` | Added | Structured component synthesis validation. |
| `src/codebase_architect/llm/providers/__init__.py` | Added | Provider package exports. |
| `src/codebase_architect/llm/providers/ollama.py` | Added | Ollama provider implementation. |
| `src/codebase_architect/llm/providers/openai_compatible.py` | Added | Generic OpenAI-compatible provider. |
| `src/codebase_architect/resources/__init__.py` | Added | Package resource module. |
| `src/codebase_architect/resources/codebase-architect-skill.md` | Added | Wheel-shipped Agent Skill template. |
| `src/codebase_architect/analyzers/javascript.py` | Modified | Improve JS/TS route/env/export detection and Mermaid safety inputs indirectly. |
| `src/codebase_architect/cli.py` | Modified | Add commands/options and error hierarchy handling. |
| `src/codebase_architect/config.py` | Modified | Versioned schema, endpoint validation, provider fields. |
| `src/codebase_architect/diagrams.py` | Modified | Generated markers, guarded writes, safer labels. |
| `src/codebase_architect/docs.py` | Modified | Shared generated-file safety helper. |
| `src/codebase_architect/pipeline.py` | Modified | Provider registry usage, output path validation, manifest config/durations. |
| `src/codebase_architect/planner.py` | Modified | Structured AI prompt/validation and context budgeting. |
| `src/codebase_architect/secret_filter.py` | Modified | Broader secret-class detection. |
| `tests/test_cli.py` | Added | CLI init/eval/skill install tests. |
| `tests/test_config.py` | Added | Config/offline validation tests. |
| `tests/test_llm_providers.py` | Added | Ollama/OpenAI-compatible mock provider and redirect tests. |
| `tests/test_llm_validation.py` | Added | Structured synthesis validation tests. |
| `tests/test_output_safety.py` | Added | Overwrite and output path safety tests. |
| `tests/test_javascript_analyzer.py` | Modified | Next route/bracket-env coverage. |
| `tests/test_security.py` | Modified | New error expectation and secret classes. |

# 4. Architecture Changes

The main structural change is replacing `src/codebase_architect/llm.py` with a provider package:

```text
src/codebase_architect/llm/
  base.py
  context.py
  http.py
  prompts.py
  registry.py
  validation.py
  providers/
    ollama.py
    openai_compatible.py
```

Updated architecture diagram:

```text
Repository
  -> scanner/analyzers
  -> CIG + evidence
  -> graph validation
  -> AIR inference
  -> optional llm provider + structured validation
  -> docs/diagrams via generated-output safety
  -> output validation + run manifest
```

# 5. AI Harness

- Provider interface: `GenerationRequest`, `GenerationResult`, `ModelMetadata`, `ModelCapabilities`, and `LLMProvider`.
- Ollama: health checks `/api/tags`, generates via `/api/generate`, requests JSON when structured output is needed.
- OpenAI-compatible: health checks `/models`, generates via `/chat/completions`, supports optional bearer token from `api_key_env`.
- Structured output: `ComponentSynthesis` JSON is parsed and validated before it becomes component summary text.
- Context budgeting: conservative character/token estimator with bounded node/edge inclusion and omission warnings.
- Validation: component IDs must match; cited evidence IDs must exist; AI-origin `VERIFIED` claims are ignored and warned.
- Fallback behavior: provider health failure records a warning and deterministic output continues.
- Caching: deterministic file-analysis cache remains implemented; structured model cache is deferred.
- Prompt-injection controls: trusted system instructions are separated from explicitly marked untrusted repository JSON. The harness gives the model no tools.

# 6. Local Model Support

| Runtime | Adapter | Tested/Mock-tested | Configuration | Notes |
|---|---|---|---|---|
| Ollama | `ollama` | Mock-tested | `provider = "ollama"`, `base_url = "http://127.0.0.1:11434"` | Real runtime not present in this environment. |
| Generic OpenAI-compatible local API | `openai-compatible` | Mock-tested | `provider = "openai-compatible"`, `base_url = "http://127.0.0.1:1234/v1"` | Covers compatible local servers; no runtime-specific claims. |
| No model | `none` | Tested | `provider = "none"` or `--no-llm` | First-class deterministic path. |

# 7. Gemma Usage

Gemma workflow is documented in:

- `README.md`
- `docs/LOCAL_MODELS.md`
- `docs/AGENT_SKILL_USAGE.md`
- `.github/skills/codebase-architect/SKILL.md`
- `src/codebase_architect/resources/codebase-architect-skill.md`

All examples use `<their-local-gemma-model-name>` and tell users to verify local runtime model names.

# 8. Agent Skill

A new user installs the CLI once, then in another repository runs:

```bash
cd my-project
codebase-architect skill install .
```

Resulting path:

```text
my-project/.github/skills/codebase-architect/SKILL.md
```

The wheel ships the skill template under `src/codebase_architect/resources/codebase-architect-skill.md`; wheel-installed `skill install` was smoke-tested.

# 9. Security Review

| Finding | Severity | Status | Test/Evidence |
|---|---|---|---|
| Remote model endpoint in offline mode | P1 | Fixed | `test_offline_rejects_remote_ollama`, `test_offline_allows_loopback_openai_compatible` |
| Remote redirect while offline | P1 | Fixed | `test_offline_redirect_to_remote_is_blocked` |
| URL credentials/query leakage | P1 | Fixed | `test_offline_rejects_userinfo_and_remote_host`; config validator |
| Provider proxy leakage | P1 | Fixed | `SafeHttpClient` uses `ProxyHandler({})` |
| Provider error body secret leakage | P1 | Fixed | HTTP error body redacted before exception |
| AI free-form hallucinated evidence | P1 | Fixed | `test_rejects_wrong_component_and_filters_fake_evidence` |
| Prompt injection strings in source | P1 | Mitigated | `codebase-architect eval` prompt-injection fixture |
| Non-generated output overwrite | P1 | Fixed | `test_refuses_to_overwrite_user_authored_doc` |
| Relative output path traversal | P1 | Fixed | `test_relative_output_cannot_escape_repository` |
| Secret filter coverage | P2 | Improved | `test_detects_common_secret_classes_without_retaining_values` |
| Generated Mermaid/SVG injection | P2 | Improved | source review: escaped SVG, cleaned Mermaid labels |

# 10. Tests

Command:

```powershell
$env:PYTHONPATH='src'; & 'C:\Users\YellankiKaushik\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
```

Result: passed. Tests passed: 21. Tests failed: 0. Duration: 1.319s in final run.

Command:

```powershell
$env:PYTHONPATH='src'; & 'C:\Users\YellankiKaushik\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall -q src
```

Result: passed.

Command:

```powershell
& '.\.tmp\wheel-venv\Scripts\codebase-architect.exe' doctor --json
```

Result: passed. Optional renderer tools `dot`, `d2`, and `mmdc` were not installed; doctor still passed because they are optional.

Command:

```powershell
& '.\.tmp\wheel-venv\Scripts\codebase-architect.exe' eval --json
```

Result: passed. Checks: hallucinated evidence rejection, prompt-injection fixture, no-LLM fixture.

Command:

```powershell
& '.\.tmp\wheel-venv\Scripts\codebase-architect.exe' providers --json
```

Result: passed.

# 11. End-to-End Self Analysis

Installed wheel command:

```powershell
& '.\.tmp\wheel-venv\Scripts\codebase-architect.exe' analyze . --no-llm --output .tmp\self-analysis-final --exclude .tmp/** --json
```

Measured result:

| Metric | Value |
|---|---:|
| discovered files | 75 |
| analyzed files | 4 |
| reused files | 71 |
| failed files | 0 |
| CIG nodes | 916 |
| CIG edges | 1954 |
| LLM calls | 0 |
| LLM failures | 0 |
| redactions | 0 |

Validation command:

```powershell
& '.\.tmp\wheel-venv\Scripts\codebase-architect.exe' validate .tmp\self-analysis-final --json
```

Result: passed with no errors and no warnings.

Earlier cold self-analysis in the same session discovered/analyzed 75 files, 0 failures, 916 nodes, and 1952 edges.

# 12. CI / Packaging

CI now includes multi-Python unit/integration tests, eval harness, CLI smoke tests, package build, and wheel install smoke.

Local packaging:

```powershell
& 'C:\Users\YellankiKaushik\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pip wheel . --no-build-isolation --no-deps -w dist
```

Result: passed. Final wheel built:

```text
dist/codebase_architect-0.1.0-py3-none-any.whl
```

`python -m build` could not be run locally because the bundled Python lacks the `build` module and the sandbox blocks dependency downloads. CI installs `build`.

Wheel install smoke:

```powershell
& '.\.tmp\wheel-venv\Scripts\python.exe' -m pip install --no-index --find-links dist --force-reinstall codebase-architect
```

Result: passed.

# 13. Documentation

User-facing docs added or rewritten:

- `README.md`
- `SECURITY.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `CODE_OF_CONDUCT.md`
- `docs/DEEP_TECHNICAL_ARCHITECTURE.md`
- `docs/GETTING_STARTED.md`
- `docs/LOCAL_MODELS.md`
- `docs/AGENT_SKILL_USAGE.md`
- `docs/CONFIGURATION.md`
- `docs/SECURITY_MODEL.md`
- `docs/TROUBLESHOOTING.md`
- `docs/PROVIDER_DEVELOPMENT.md`
- `docs/ANALYZER_DEVELOPMENT.md`
- `docs/PERFORMANCE.md`

# 14. Remaining Limitations

Known static-analysis limitations:

- Cross-file import/export resolution is still shallow.
- Python call targets remain mostly unresolved/inferred.
- JS/TS analysis is still structural regex analysis, not a semantic TypeScript compiler model.
- Dynamic imports, reflection, generated code, metaprogramming, runtime DI, and external systems remain partial or unknown.

Language limitations:

- Implemented analyzers cover Python, JavaScript, TypeScript, and selected config files only.

Model limitations:

- Real Ollama/OpenAI-compatible runtimes were not available locally; providers are mock-tested.
- Structured synthesis cache is not implemented.
- Model-backed evaluations are optional future work.

Performance limitations:

- No dedicated benchmark command exists yet.
- Performance methodology is documented in `docs/PERFORMANCE.md`.

Security assumptions:

- Regex-based secret detection is not complete DLP.
- Local model runtime is trusted as part of the user's local environment.
- OS filesystem permissions are assumed.

Future work:

- richer graph relationship resolution
- optional semantic parser backends
- optional D2/Graphviz renderers
- larger fixture corpus
- model-backed evaluation suite

# 15. Deferred Work

- Full whole-repository semantic JS/TS/Python resolution: deferred because it needs a larger parser/resolver design.
- D2/Graphviz renderers: deferred; current implementation emits Mermaid and SVG source.
- Model synthesis cache: deferred to avoid persisting prompt/response content before a privacy design is finalized.
- Dedicated benchmark command: deferred; documented run-manifest methodology added.
- Runtime-specific LM Studio/llama.cpp/vLLM adapters: deferred because the generic OpenAI-compatible adapter is the implemented compatibility layer.

# 16. Breaking Changes

- `src/codebase_architect/llm.py` became the `src/codebase_architect/llm/` package. Public import `from codebase_architect.llm import provider_from_config` still works.
- Config now rejects unknown keys.
- `--offline` now allows `openai-compatible` only when endpoint validation passes.
- Provider URLs with credentials, query strings, fragments, unsupported schemes, or non-loopback hosts in offline mode are rejected.
- Non-generated Markdown/diagram outputs are protected unless `output.overwrite = "force"` is set.

# 17. Manual Verification Steps

1. `python -m pip install -e .`
2. `python -m unittest discover -s tests -v`
3. `codebase-architect doctor`
4. `codebase-architect providers`
5. `codebase-architect eval`
6. `codebase-architect analyze . --no-llm --output .tmp/manual-check --exclude .tmp/**`
7. `codebase-architect validate .tmp/manual-check`
8. In a separate fixture repo: `codebase-architect skill install .`
9. Optional if Ollama is installed: `codebase-architect doctor --provider ollama --model <their-local-model-name> --offline`

# 18. Git Diff Summary

Pre-report `git status --short`:

```text
 M .codebase-architect.toml.example
 M .github/skills/codebase-architect/SKILL.md
 M .github/workflows/ci.yml
 M .gitignore
 M CONTRIBUTING.md
 M README.md
 M SECURITY.md
 M docs/DEEP_TECHNICAL_ARCHITECTURE.md
 M pyproject.toml
 M src/codebase_architect/analyzers/javascript.py
 M src/codebase_architect/cli.py
 M src/codebase_architect/config.py
 M src/codebase_architect/diagrams.py
 M src/codebase_architect/docs.py
 D src/codebase_architect/llm.py
 M src/codebase_architect/pipeline.py
 M src/codebase_architect/planner.py
 M src/codebase_architect/secret_filter.py
 M tests/test_javascript_analyzer.py
 M tests/test_security.py
?? .github/ISSUE_TEMPLATE/
?? .github/pull_request_template.md
?? CHANGELOG.md
?? CODE_OF_CONDUCT.md
?? docs/AGENT_SKILL_USAGE.md
?? docs/ANALYZER_DEVELOPMENT.md
?? docs/CONFIGURATION.md
?? docs/GETTING_STARTED.md
?? docs/LOCAL_MODELS.md
?? docs/PERFORMANCE.md
?? docs/PROVIDER_DEVELOPMENT.md
?? docs/SECURITY_MODEL.md
?? docs/TROUBLESHOOTING.md
?? src/codebase_architect/errors.py
?? src/codebase_architect/eval.py
?? src/codebase_architect/file_safety.py
?? src/codebase_architect/llm/
?? src/codebase_architect/resources/
?? tests/test_cli.py
?? tests/test_config.py
?? tests/test_llm_providers.py
?? tests/test_llm_validation.py
?? tests/test_output_safety.py
```

Pre-report `git diff --stat`:

```text
 .codebase-architect.toml.example               |   10 +-
 .github/skills/codebase-architect/SKILL.md     |    4 +-
 .github/workflows/ci.yml                       |   26 +-
 .gitignore                                     |    1 +
 CONTRIBUTING.md                                |   22 +-
 README.md                                      |  227 +-
 SECURITY.md                                    |   45 +-
 docs/DEEP_TECHNICAL_ARCHITECTURE.md            | 5654 +-----------------------
 pyproject.toml                                 |   25 +-
 src/codebase_architect/analyzers/javascript.py |   46 +-
 src/codebase_architect/cli.py                  |   96 +-
 src/codebase_architect/config.py               |  122 +-
 src/codebase_architect/diagrams.py             |   32 +-
 src/codebase_architect/docs.py                 |   23 +-
 src/codebase_architect/llm.py                  |   66 -
 src/codebase_architect/pipeline.py             |   28 +-
 src/codebase_architect/planner.py              |   55 +-
 src/codebase_architect/secret_filter.py        |   34 +-
 tests/test_javascript_analyzer.py              |   11 +
 tests/test_security.py                         |   15 +-
 20 files changed, 677 insertions(+), 5865 deletions(-)
```

Untracked new files are listed in section 3. The report itself is also a new untracked file.

# 19. Final Verdict

READY FOR REVIEW

The implementation is ready for maintainer review as an alpha-hardening diff. It is not yet ready to claim complete production/beta maturity because deeper cross-file semantic analysis, optional renderer backends, structured model caching, larger fixture corpora, and real-runtime model integration tests remain deferred.
