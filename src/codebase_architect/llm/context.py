from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from ..graph import CodeGraph


PROMPT_TEMPLATE_VERSION = "component-synthesis-v2"


@dataclass(slots=True)
class ContextBudget:
    max_input_tokens: int
    max_nodes: int = 120
    max_edges: int = 260
    omitted: list[str] = field(default_factory=list)


def estimate_tokens(text: str) -> int:
    # Conservative enough for local-model budgeting without a tokenizer dependency.
    return max(1, (len(text) + 3) // 4)


def default_budget(max_context_tokens: int | None) -> ContextBudget:
    limit = max_context_tokens or 8192
    return ContextBudget(max_input_tokens=max(1024, int(limit * 0.65)))


def bounded_json(value: Any, budget: ContextBudget) -> str:
    text = json.dumps(value, indent=2, sort_keys=True)
    if estimate_tokens(text) <= budget.max_input_tokens:
        return text
    target_chars = budget.max_input_tokens * 4
    budget.omitted.append("context truncated to configured budget")
    return text[:target_chars] + "\n/* TRUNCATED: additional graph context omitted */"


def context_cache_key(component: dict, graph: CodeGraph, model_key: str) -> str:
    payload = {
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "model": model_key,
        "component": component,
        "graph_nodes": sorted(graph.nodes),
        "graph_edges": sorted(graph.edges),
    }
    return sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
