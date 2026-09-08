from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from .models import FileAnalysis, SCHEMA_VERSION

class AnalysisCache:
    def __init__(self, repository: Path):
        self.path = repository / ".codebase-architect" / "cache-v1.json"
        self.data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists(): return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if raw.get("schema_version") == SCHEMA_VERSION:
                self.data = raw.get("files", {})
        except (OSError, json.JSONDecodeError):
            self.data = {}

    def get(self, path: str, content_hash: str) -> FileAnalysis | None:
        raw = self.data.get(path)
        if not raw or raw.get("content_hash") != content_hash: return None
        try:
            analysis = FileAnalysis.from_dict(raw["analysis"])
            if _stale_js_structural_cache(path, analysis):
                return None
            return analysis
        except (KeyError, TypeError, ValueError): return None

    def put(self, analysis: FileAnalysis) -> None:
        self.data[analysis.path] = {"content_hash": analysis.content_hash, "analysis": analysis.to_dict()}

    def remove_missing(self, live_paths: set[str]) -> None:
        self.data = {path: value for path, value in self.data.items() if path in live_paths}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": SCHEMA_VERSION, "files": self.data}
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp.replace(self.path)

def _stale_js_structural_cache(path: str, analysis: FileAnalysis) -> bool:
    suffix = Path(path).suffix.lower()
    if suffix not in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
        return False
    if analysis.backend != "structural-js-ts":
        return False
    return all(importlib.util.find_spec(name) for name in ("tree_sitter", "tree_sitter_javascript", "tree_sitter_typescript"))
