from __future__ import annotations

from pathlib import Path
from ..models import FileAnalysis, FileRecord
from . import config_files, javascript, python

CONFIG_NAMES = {"package.json", "requirements.txt", "pyproject.toml", "Dockerfile", "docker-compose.yml", "docker-compose.yaml"}

def supported_language(record: FileRecord) -> bool:
    name = Path(record.path).name
    return record.language in {"python", "javascript", "typescript"} or name in CONFIG_NAMES or record.path.startswith(".github/workflows/")

def analyze_file(record: FileRecord, source: str) -> FileAnalysis:
    name = Path(record.path).name
    if record.language == "python":
        return python.analyze(record.path, record.content_hash, source)
    if record.language in {"javascript", "typescript"}:
        return javascript.analyze(record.path, record.content_hash, source, record.language)
    return config_files.analyze(record.path, record.content_hash, source, record.language)
