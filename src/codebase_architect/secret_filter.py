from __future__ import annotations

import re
from dataclasses import dataclass

@dataclass(slots=True)
class RedactionResult:
    text: str
    count: int

NAMED_SECRET = re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*['\"]?([^\s'\";,]{8,})")
TOKEN_PATTERNS = [
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
]

def redact(text: str) -> RedactionResult:
    count = 0
    def named(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"{match.group(1)}=<REDACTED>"
    result = NAMED_SECRET.sub(named, text)
    for pattern in TOKEN_PATTERNS:
        result, n = pattern.subn("<REDACTED>", result)
        count += n
    return RedactionResult(result, count)

def contains_secret(text: str) -> bool:
    return bool(NAMED_SECRET.search(text) or any(p.search(text) for p in TOKEN_PATTERNS))
