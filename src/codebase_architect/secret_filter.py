from __future__ import annotations

import re
from dataclasses import dataclass

@dataclass(slots=True)
class RedactionResult:
    text: str
    count: int
    types: dict[str, int] | None = None

NAMED_SECRET = re.compile(r"(?i)\b([A-Z0-9_]*(?:api[_-]?key|secret|password|passwd|pwd|token|webhook)[A-Z0-9_-]*)\b\s*[:=]\s*['\"]?([^\s'\";,]{8,})")
TOKEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("database_url", re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^:\s/@]+:[^@\s]+@[^ \n\r\t]+")),
    ("generic_connection_string", re.compile(r"(?i)\b(?:password|pwd)=([^; \n\r\t]{8,})")),
]

def redact(text: str) -> RedactionResult:
    count = 0
    types: dict[str, int] = {}
    def add(kind: str, amount: int = 1) -> None:
        nonlocal count
        count += amount
        types[kind] = types.get(kind, 0) + amount
    def named(match: re.Match[str]) -> str:
        add("named_secret")
        return f"{match.group(1)}=<REDACTED>"
    result = NAMED_SECRET.sub(named, text)
    for kind, pattern in TOKEN_PATTERNS:
        result, n = pattern.subn("<REDACTED>", result)
        if n:
            add(kind, n)
    return RedactionResult(result, count, types)

def contains_secret(text: str) -> bool:
    return bool(NAMED_SECRET.search(text) or any(pattern.search(text) for _, pattern in TOKEN_PATTERNS))
