from __future__ import annotations

import fnmatch
import hashlib
import os
from pathlib import Path

from .config import AnalysisConfig
from .models import FileRecord

LANGUAGE_BY_SUFFIX = {
    ".py": "python", ".pyi": "python", ".js": "javascript", ".jsx": "javascript",
    ".mjs": "javascript", ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".json": "json", ".toml": "toml", ".yaml": "yaml", ".yml": "yaml",
    ".sql": "sql", ".md": "markdown", ".sh": "shell",
}
SPECIAL_NAMES = {
    "Dockerfile": "docker", "docker-compose.yml": "yaml", "docker-compose.yaml": "yaml",
    "requirements.txt": "requirements", "pyproject.toml": "toml", "package.json": "json",
}
GENERATED_PARTS = {"node_modules", "vendor", "dist", "build", "coverage", ".next", "target", "bin", "obj"}

def discover_files(repository: Path, config: AnalysisConfig) -> list[FileRecord]:
    repository = repository.resolve()
    if not repository.is_dir():
        raise FileNotFoundError(f"Repository path does not exist or is not a directory: {repository}")
    records: list[FileRecord] = []
    focus = _normalize_focus(config.focus)
    for current, dirs, names in os.walk(repository, followlinks=False):
        current_path = Path(current)
        dirs[:] = [d for d in dirs if not _is_excluded((current_path / d).relative_to(repository).as_posix() + "/", config.exclude)]
        for name in names:
            absolute = current_path / name
            try:
                if absolute.is_symlink():
                    resolved = absolute.resolve(strict=False)
                    try:
                        resolved.relative_to(repository)
                    except ValueError:
                        continue
                relative = absolute.relative_to(repository).as_posix()
            except (OSError, ValueError):
                continue
            if focus and not (relative == focus or relative.startswith(focus.rstrip("/") + "/")):
                continue
            if _is_excluded(relative, config.exclude):
                continue
            try:
                stat = absolute.stat()
            except OSError:
                continue
            if stat.st_size > config.max_file_bytes or _looks_binary(absolute):
                continue
            language = SPECIAL_NAMES.get(name) or LANGUAGE_BY_SUFFIX.get(absolute.suffix.lower(), "text")
            generated = any(part in GENERATED_PARTS for part in Path(relative).parts)
            try:
                digest = _sha256(absolute)
            except OSError:
                continue
            records.append(FileRecord(relative, str(absolute), stat.st_size, digest, language, generated))
    records.sort(key=lambda r: r.path)
    return records

def _normalize_focus(value: str | None) -> str | None:
    return value.replace("\\", "/").strip("/") if value else None

def _is_excluded(relative: str, patterns: list[str]) -> bool:
    normalized = relative.replace("\\", "/").lstrip("./")
    for pattern in patterns:
        p = pattern.replace("\\", "/").lstrip("./")
        if fnmatch.fnmatch(normalized, p) or fnmatch.fnmatch(normalized, p.rstrip("/**")):
            return True
        first = p.split("/", 1)[0]
        if first and first in normalized.split("/") and (p.endswith("/**") or p == first):
            return True
    return False

def _looks_binary(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:4096]
    except OSError:
        return True
    if b"\x00" in sample:
        return True
    if not sample:
        return False
    controls = sum(1 for b in sample if b < 9 or 13 < b < 32)
    return controls / len(sample) > 0.08

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
