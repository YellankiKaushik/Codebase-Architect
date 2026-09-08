from __future__ import annotations
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from .analyzers import analyze_file
from .architecture import infer_architecture
from .cache import AnalysisCache
from .config import Config
from .diagrams import generate_diagrams
from .file_safety import resolve_output_path
from .frameworks import detect_frameworks
from .docs import write_documentation
from .gitutils import current_commit
from .graph import CodeGraph
from .llm import provider_from_config
from .models import RunStats
from .planner import synthesize_components
from .resolver import resolve_graph
from .scanner import discover_files
from .validate import validate_graph, validate_output

def run_analysis(repository:Path,config:Config,use_llm:bool=True)->dict:
    started=time.time();phase_started=started;phase_durations={};repository=repository.resolve();config.validate();stats=RunStats()
    records=discover_files(repository,config.analysis);stats.files_discovered=len(records)
    phase_durations["scan_seconds"]=round(time.time()-phase_started,3);phase_started=time.time()
    cache=AnalysisCache(repository);graph=CodeGraph();stack=set();warnings=[]
    live_paths={r.path for r in records}
    for record in records:
        cached=cache.get(record.path,record.content_hash)
        if cached is not None:
            stats.files_reused+=1;graph.add_many(cached.nodes,cached.edges);stack.update(cached.stack);warnings.extend(cached.warnings);_count_analyzer(stats,cached.capability,cached.backend);continue
        try:
            raw=Path(record.absolute_path).read_text(encoding="utf-8",errors="replace")
            analysis=analyze_file(record,raw);cache.put(analysis);graph.add_many(analysis.nodes,analysis.edges);stack.update(analysis.stack);warnings.extend(analysis.warnings);stats.files_analyzed+=1;_count_analyzer(stats,analysis.capability,analysis.backend)
        except Exception as exc:
            stats.files_failed+=1;warnings.append(f"{record.path}: analyzer failure: {exc}")
    cache.remove_missing(live_paths);cache.save()
    phase_durations["analysis_seconds"]=round(time.time()-phase_started,3);phase_started=time.time()
    resolver_report=resolve_graph(repository,graph);stats.resolver_edges_added=resolver_report["edges_added"];warnings.extend(resolver_report.get("warnings", []))
    framework_report=detect_frameworks(graph,stack)
    phase_durations["resolver_seconds"]=round(time.time()-phase_started,3);phase_started=time.time()
    stats.graph_nodes=len(graph.nodes);stats.graph_edges=len(graph.edges)
    graph_report=validate_graph(graph);warnings.extend(graph_report.warnings)
    if graph_report.errors: raise RuntimeError("Graph validation failed: "+"; ".join(graph_report.errors[:10]))
    air=infer_architecture(repository,graph,stack,warnings)
    air.frameworks=framework_report
    phase_durations["architecture_seconds"]=round(time.time()-phase_started,3);phase_started=time.time()
    if use_llm and config.model.provider not in {"","none"}:
        synthesize_components(air,graph,provider_from_config(config.model,config),stats)
    phase_durations["synthesis_seconds"]=round(time.time()-phase_started,3);phase_started=time.time()
    output=resolve_output_path(repository, config.output.path)
    output.mkdir(parents=True,exist_ok=True)
    commit=current_commit(repository)
    force_output = config.output.overwrite == "force"
    created=write_documentation(repository,output,air,graph,stats,commit,force=force_output)
    phase_durations["docs_seconds"]=round(time.time()-phase_started,3);phase_started=time.time()
    created.extend(generate_diagrams(air,output/"diagrams",config.output.diagrams,force=force_output))
    phase_durations["diagrams_seconds"]=round(time.time()-phase_started,3);phase_started=time.time()
    manifest={
        "schema_version":"1","tool_version":"0.1.0",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "repository":str(repository),"commit":commit,
        "effective_config":{
            "analysis":asdict(config.analysis),
            "model":{
                "provider":config.model.provider,
                "name":config.model.name,
                "base_url":_safe_base_url(config.model.base_url),
                "api_key_env":config.model.api_key_env,
                "timeout_seconds":config.model.timeout_seconds,
                "max_context_tokens":config.model.max_context_tokens,
                "retry_attempts":config.model.retry_attempts,
            },
            "security":asdict(config.security),"output":asdict(config.output),
        },
        "stats":stats.to_dict(),
        "created_artifacts":[str(p.relative_to(output)) for p in created],
        "phase_durations":phase_durations,
        "duration_seconds":round(time.time()-started,3),
    }
    manifest_path=output/"evidence"/"run-manifest.json";manifest_path.write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    report=validate_output(output);validation_path=output/"validation-report.md";validation_path.write_text(report.markdown(),encoding="utf-8")
    phase_durations["validation_seconds"]=round(time.time()-phase_started,3)
    if not report.ok: raise RuntimeError("Generated output validation failed: "+"; ".join(report.errors[:10]))
    return {"output":str(output),"stats":stats.to_dict(),"manifest":str(manifest_path),"validation":str(validation_path)}

def _safe_base_url(value:str)->str:
    if "@" in value and "://" in value:
        scheme,rest=value.split("://",1);rest=rest.split("@",1)[1];return f"{scheme}://{rest}"
    return value

def _count_analyzer(stats: RunStats, capability: str, backend: str) -> None:
    stats.analyzer_capabilities[capability] = stats.analyzer_capabilities.get(capability, 0) + 1
    stats.analyzer_backends[backend] = stats.analyzer_backends.get(backend, 0) + 1
