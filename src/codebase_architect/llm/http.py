from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urljoin

from ..config import validate_endpoint
from ..errors import ProviderProtocolError, ProviderUnavailableError, SecurityPolicyError
from ..secret_filter import redact


MAX_RESPONSE_BYTES = 2_000_000


@dataclass(slots=True)
class HttpResult:
    status: int
    body: bytes
    headers: dict[str, str]


class OfflineAwareRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, offline: bool):
        self.offline = offline
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if self.offline:
            validate_endpoint(newurl, offline=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class SafeHttpClient:
    def __init__(self, base_url: str, *, timeout: int, offline: bool, retry_attempts: int = 1):
        validate_endpoint(base_url, offline=offline)
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.offline = offline
        self.retry_attempts = retry_attempts
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            OfflineAwareRedirectHandler(offline),
        )

    def get_json(self, path: str, headers: dict[str, str] | None = None) -> dict:
        result = self.request("GET", path, headers=headers)
        return _loads_json(result.body)

    def post_json(self, path: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
        body = json.dumps(payload).encode("utf-8")
        merged = {"Content-Type": "application/json", **(headers or {})}
        result = self.request("POST", path, data=body, headers=merged)
        return _loads_json(result.body)

    def request(self, method: str, path: str, data: bytes | None = None, headers: dict[str, str] | None = None) -> HttpResult:
        url = urljoin(self.base_url, path.lstrip("/"))
        if self.offline:
            validate_endpoint(url, offline=True)
        attempts = self.retry_attempts + 1
        last_exc: Exception | None = None
        for attempt in range(attempts):
            request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    body = response.read(MAX_RESPONSE_BYTES + 1)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise ProviderProtocolError("provider response exceeded maximum supported size")
                    return HttpResult(response.status, body, dict(response.headers.items()))
            except urllib.error.HTTPError as exc:
                detail = redact(exc.read(min(MAX_RESPONSE_BYTES, 4096)).decode("utf-8", errors="replace")).text
                if exc.code in {408, 409, 425, 429, 500, 502, 503, 504} and attempt + 1 < attempts:
                    last_exc = exc
                    time.sleep(0.15 * (attempt + 1))
                    continue
                raise ProviderUnavailableError(f"provider HTTP {exc.code}: {detail[:500]}") from exc
            except SecurityPolicyError:
                raise
            except (OSError, urllib.error.URLError) as exc:
                last_exc = exc
                if attempt + 1 < attempts:
                    time.sleep(0.15 * (attempt + 1))
                    continue
                raise ProviderUnavailableError(f"provider unavailable: {exc}") from exc
        raise ProviderUnavailableError(f"provider unavailable: {last_exc}")


def _loads_json(body: bytes) -> dict:
    try:
        raw = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ProviderProtocolError(f"provider returned invalid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProviderProtocolError("provider returned JSON that is not an object")
    return raw
