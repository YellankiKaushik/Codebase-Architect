from __future__ import annotations
import argparse
import importlib.resources
import json
import shutil
import sys
from dataclasses import asdict, replace
from pathlib import Path
from . import __version__
from .config import Config
from .errors import CodebaseArchitectError
from .graph import CodeGraph
from .llm import provider_from_config, provider_types
from .pipeline import run_analysis
from .validate import validate_output

def build_parser()->argparse.ArgumentParser:
    parser=argparse.ArgumentParser(prog="codebase-architect",description="Evidence-backed local codebase documentation and architecture generation.")
    parser.add_argument("--version",action="version",version=__version__)
    sub=parser.add_subparsers(dest="command",required=True)
    for name,help_text in (("analyze","Analyze repository and generate docs/diagrams"),("update","Incrementally re-analyze repository"),("diagrams","Generate/update architecture diagrams"),("benchmark","Run analysis and emit timing/cache metrics")):
        p=sub.add_parser(name,help=help_text);_analysis_args(p)
        if name in {"diagrams", "benchmark"}: p.set_defaults(no_llm=True)
    p=sub.add_parser("validate",help="Validate generated documentation directory");p.add_argument("path",nargs="?",default="docs/codebase");p.add_argument("--json",action="store_true",dest="json_output")
    p=sub.add_parser("inspect",help="Analyze then inspect graph elements");p.add_argument("path",nargs="?",default=".");p.add_argument("--kind");p.add_argument("--name")
    p=sub.add_parser("doctor",help="Check local installation and optional tools");p.add_argument("--provider",default="none");p.add_argument("--model",default="");p.add_argument("--base-url",default="http://127.0.0.1:11434");p.add_argument("--api-key-env");p.add_argument("--offline",action="store_true");p.add_argument("--json",action="store_true",dest="json_output")
    p=sub.add_parser("providers",help="List supported provider types");p.add_argument("--json",action="store_true",dest="json_output")
    p=sub.add_parser("models",help="Check configured provider and list models when available");p.add_argument("--provider",default="none",choices=["none","ollama","openai-compatible"]);p.add_argument("--model",default="");p.add_argument("--base-url",default="http://127.0.0.1:11434");p.add_argument("--api-key-env");p.add_argument("--offline",action="store_true");p.add_argument("--json",action="store_true",dest="json_output")
    p=sub.add_parser("init",help="Create a starter .codebase-architect.toml");p.add_argument("path",nargs="?",default=".");p.add_argument("--force",action="store_true");p.add_argument("--json",action="store_true",dest="json_output")
    p=sub.add_parser("eval",help="Run deterministic built-in evaluation checks");p.add_argument("--json",action="store_true",dest="json_output")
    skill=sub.add_parser("skill",help="Manage Agent Skill installation");skill_sub=skill.add_subparsers(dest="skill_command",required=True);install=skill_sub.add_parser("install",help="Install the Codebase Architect Agent Skill into a repository");install.add_argument("path",nargs="?",default=".");install.add_argument("--force",action="store_true");install.add_argument("--json",action="store_true",dest="json_output")
    return parser

def _analysis_args(p):
    p.add_argument("path",nargs="?",default=".");p.add_argument("--config");p.add_argument("--output");p.add_argument("--detail",choices=["quick","standard","deep","exhaustive"]);p.add_argument("--focus");p.add_argument("--exclude",action="append",default=[]);p.add_argument("--max-file-bytes",type=int);p.add_argument("--provider",choices=["none","ollama","openai-compatible"]);p.add_argument("--model");p.add_argument("--base-url");p.add_argument("--api-key-env");p.add_argument("--timeout-seconds",type=int);p.add_argument("--max-context-tokens",type=int);p.add_argument("--retry-attempts",type=int);p.add_argument("--offline",action="store_true");p.add_argument("--no-llm",action="store_true");p.add_argument("--diagrams");p.add_argument("--json",action="store_true",dest="json_output")

def main(argv:list[str]|None=None)->None:
    args=build_parser().parse_args(argv)
    try:
        if args.command in {"analyze","update","diagrams"}: _emit(_run(args),args.json_output);return
        if args.command=="benchmark": _emit(_benchmark(args),args.json_output);return
        if args.command=="validate":
            report=validate_output(Path(args.path).resolve());_emit({"ok":report.ok,"errors":report.errors,"warnings":report.warnings},args.json_output)
            if not report.ok: raise SystemExit(2)
            return
        if args.command=="inspect": _inspect(args);return
        if args.command=="doctor": _doctor(args);return
        if args.command=="providers": _providers(args);return
        if args.command=="models": _models(args);return
        if args.command=="init": _init(args);return
        if args.command=="eval": _eval(args);return
        if args.command=="skill" and args.skill_command=="install": _skill_install(args);return
    except (CodebaseArchitectError, ValueError,FileNotFoundError,RuntimeError) as exc:
        print(f"error: {exc}",file=sys.stderr);raise SystemExit(2) from exc

def _run(args)->dict:
    repo=Path(args.path).resolve();explicit=Path(args.config).resolve() if args.config else None;config=Config.load(repo,explicit)
    if args.output: config.output=replace(config.output,path=args.output)
    if args.detail: config.analysis=replace(config.analysis,detail=args.detail)
    if args.focus: config.analysis=replace(config.analysis,focus=args.focus)
    if args.exclude: config.analysis=replace(config.analysis,exclude=list(dict.fromkeys(config.analysis.exclude+args.exclude)))
    if args.max_file_bytes: config.analysis=replace(config.analysis,max_file_bytes=args.max_file_bytes)
    if args.provider is not None: config.model=replace(config.model,provider=args.provider)
    if args.model is not None: config.model=replace(config.model,name=args.model)
    if args.base_url is not None: config.model=replace(config.model,base_url=args.base_url)
    if args.api_key_env is not None: config.model=replace(config.model,api_key_env=args.api_key_env)
    if args.timeout_seconds is not None: config.model=replace(config.model,timeout_seconds=args.timeout_seconds)
    if args.max_context_tokens is not None: config.model=replace(config.model,max_context_tokens=args.max_context_tokens)
    if args.retry_attempts is not None: config.model=replace(config.model,retry_attempts=args.retry_attempts)
    if args.offline: config.security=replace(config.security,offline=True)
    if args.diagrams: config.output=replace(config.output,diagrams=[x.strip() for x in args.diagrams.split(",") if x.strip()])
    config.validate();return run_analysis(repo,config,use_llm=not args.no_llm)

def _benchmark(args)->dict:
    if not args.output:
        args.output = ".tmp/benchmark-analysis"
    result = _run(args)
    manifest = json.loads((Path(result["manifest"])).read_text(encoding="utf-8"))
    stats = manifest.get("stats", {})
    duration = float(manifest.get("duration_seconds") or 0)
    discovered = int(stats.get("files_discovered") or 0)
    reused = int(stats.get("files_reused") or 0)
    return {
        "ok": True,
        "output": result["output"],
        "duration_seconds": duration,
        "files_per_second": round(discovered / duration, 3) if duration > 0 else 0,
        "cache_hit_rate": round(reused / discovered, 3) if discovered else 0,
        "phase_durations": manifest.get("phase_durations", {}),
        "stats": stats,
        "manifest": result["manifest"],
        "validation": result["validation"],
    }

def _inspect(args)->None:
    repo=Path(args.path).resolve();config=Config.load(repo);config.model=replace(config.model,provider="none");result=run_analysis(repo,config,use_llm=False)
    raw=json.loads((Path(result["output"])/"evidence"/"code-intelligence-graph.json").read_text(encoding="utf-8"));graph=CodeGraph.from_dict(raw);nodes=list(graph.nodes.values())
    if args.kind: nodes=[n for n in nodes if n.kind.upper()==args.kind.upper()]
    if args.name: nodes=[n for n in nodes if args.name.lower() in n.name.lower()]
    print(json.dumps([n.to_dict() for n in nodes],indent=2))

def _doctor(args)->None:
    checks={"python":{"ok":sys.version_info>=(3,11),"detail":sys.version.split()[0]},"git":{"ok":shutil.which("git") is not None,"detail":shutil.which("git")},"graphviz_dot":{"ok":shutil.which("dot") is not None,"detail":shutil.which("dot")},"d2":{"ok":shutil.which("d2") is not None,"detail":shutil.which("d2")},"mermaid_cli":{"ok":shutil.which("mmdc") is not None,"detail":shutil.which("mmdc")}}
    if args.provider!="none":
        cfg=Config();cfg.model=replace(cfg.model,provider=args.provider,name=args.model,base_url=args.base_url,api_key_env=args.api_key_env);cfg.security=replace(cfg.security,offline=args.offline);cfg.validate();ok,detail=provider_from_config(cfg.model,cfg).health();checks["model_provider"]={"ok":ok,"detail":detail}
    overall=checks["python"]["ok"] and checks.get("model_provider",{"ok":True})["ok"];_emit({"ok":overall,"version":__version__,"checks":checks},args.json_output)
    if not overall: raise SystemExit(2)

def _providers(args)->None:
    _emit({"ok":True,"providers":provider_types()},args.json_output)

def _models(args)->None:
    cfg=Config();cfg.model=replace(cfg.model,provider=args.provider,name=args.model,base_url=args.base_url,api_key_env=args.api_key_env);cfg.security=replace(cfg.security,offline=args.offline);cfg.validate()
    provider=provider_from_config(cfg.model,cfg)
    ok,detail=provider.health()
    _emit({"ok":ok,"provider":provider.metadata.provider,"model":provider.metadata.model,"endpoint":provider.metadata.endpoint,"capabilities":asdict(provider.metadata.capabilities),"detail":detail},args.json_output)
    if not ok: raise SystemExit(2)

def _init(args)->None:
    root=Path(args.path).resolve()
    if not root.exists(): root.mkdir(parents=True)
    path=root/".codebase-architect.toml"
    if path.exists() and not args.force:
        raise RuntimeError(f"Refusing to overwrite existing config: {path}")
    path.write_text(_starter_config(),encoding="utf-8")
    _emit({"ok":True,"path":str(path)},args.json_output)

def _eval(args)->None:
    from .eval import run_evaluations
    _emit(run_evaluations(),args.json_output)

def _skill_install(args)->None:
    target=Path(args.path).resolve()
    if not target.is_dir():
        raise FileNotFoundError(f"Target repository does not exist: {target}")
    try:
        content=importlib.resources.files("codebase_architect.resources").joinpath("codebase-architect-skill.md").read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        source=Path.cwd()/".github"/"skills"/"codebase-architect"/"SKILL.md"
        if not source.exists():
            raise RuntimeError("Bundled Agent Skill template is missing") from exc
        content=source.read_text(encoding="utf-8")
    destination=target/".github"/"skills"/"codebase-architect"/"SKILL.md"
    if destination.exists() and not args.force:
        raise RuntimeError(f"Refusing to overwrite existing skill without --force: {destination}")
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(content,encoding="utf-8")
    _emit({"ok":True,"path":str(destination)},args.json_output)

def _starter_config()->str:
    return """version = 1

[analysis]
detail = "deep"
max_file_bytes = 1000000
exclude = ["node_modules/**", "vendor/**", "dist/**", "build/**", "coverage/**"]

[model]
provider = "none"
name = ""
base_url = "http://127.0.0.1:11434"
timeout_seconds = 120
retry_attempts = 1
# max_context_tokens = 8192
# api_key_env = "LOCAL_MODEL_API_KEY"

[security]
offline = true
persist_model_cache = false

[output]
path = "docs/codebase"
diagrams = ["technical", "dependency", "dataflow", "c4", "runtime", "visual"]
overwrite = "generated-only"
"""

def _emit(payload:dict,as_json:bool)->None:
    if as_json: print(json.dumps(payload,indent=2));return
    if "output" in payload:
        s=payload.get("stats",{});print(f"Generated: {payload['output']}");print(f"Files: {s.get('files_discovered',0)} discovered, {s.get('files_analyzed',0)} analyzed, {s.get('files_reused',0)} reused");print(f"Graph: {s.get('graph_nodes',0)} nodes / {s.get('graph_edges',0)} edges")
    else: print(json.dumps(payload,indent=2))
