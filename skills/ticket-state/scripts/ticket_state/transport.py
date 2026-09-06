"""HTTP transport with redirect refusal and credential-safe failures."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from .errors import RemoteError


@dataclass(frozen=True, slots=True)
class HttpRequest:
    method: str
    url: str
    headers: Mapping[str, str]
    body: bytes | None = None
    is_mutation: bool = False


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes

    def json(self) -> object:
        try:
            return json.loads(self.body.decode("utf-8")) if self.body else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RemoteError("remote response was not valid UTF-8 JSON") from exc


class Transport(Protocol):
    def send(self, request: HttpRequest) -> HttpResponse: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class UrlLibTransport:
    def __init__(self, *, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self._opener = urllib.request.build_opener(_NoRedirect)

    def send(self, request: HttpRequest) -> HttpResponse:
        raw = urllib.request.Request(
            request.url,
            data=request.body,
            headers=dict(request.headers),
            method=request.method,
        )
        try:
            with self._opener.open(raw, timeout=self.timeout) as response:
                return HttpResponse(
                    status=response.status,
                    headers=dict(response.headers.items()),
                    body=response.read(),
                )
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            if 300 <= status < 400:
                raise RemoteError(
                    "remote redirect was refused",
                    status=status,
                    result_unknown=request.is_mutation,
                    mutation_attempted=request.is_mutation,
                ) from exc
            ambiguous = request.is_mutation and status >= 500
            raise RemoteError(
                f"remote request failed with HTTP {status}",
                status=status,
                retryable=(status == 429 or status >= 500) and not request.is_mutation,
                result_unknown=ambiguous,
                mutation_attempted=request.is_mutation,
            ) from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError) as exc:
            raise RemoteError(
                "remote connection failed",
                retryable=not request.is_mutation,
                result_unknown=request.is_mutation,
                mutation_attempted=request.is_mutation,
            ) from exc


class FixtureTransport:
    """Exact-match, read-only HTTP fixture transport for public CLI evals."""

    def __init__(self, path: Path) -> None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RemoteError(f"cannot load transport fixture: {exc}") from exc
        if not isinstance(value, dict) or set(value) != {"schema_version", "responses"}:
            raise RemoteError("transport fixture has invalid root fields")
        if value["schema_version"] != 1 or not isinstance(value["responses"], list):
            raise RemoteError("transport fixture has invalid version or responses")
        self._responses: dict[tuple[str, str], HttpResponse] = {}
        for item in value["responses"]:
            if not isinstance(item, dict) or set(item) != {"method", "url", "status", "headers", "body"}:
                raise RemoteError("transport fixture response has invalid fields")
            method = item["method"]
            url = item["url"]
            status = item["status"]
            headers = item["headers"]
            if method != "GET" or not isinstance(url, str) or not url.startswith("https://"):
                raise RemoteError("transport fixtures may contain exact HTTPS GET responses only")
            if not isinstance(status, int) or isinstance(status, bool) or not isinstance(headers, dict):
                raise RemoteError("transport fixture response status/headers are invalid")
            key = (method, url)
            if key in self._responses:
                raise RemoteError("transport fixture contains duplicate request keys")
            body_value: Any = item["body"]
            body = json.dumps(body_value, ensure_ascii=False).encode("utf-8")
            self._responses[key] = HttpResponse(status, {str(k): str(v) for k, v in headers.items()}, body)

    def send(self, request: HttpRequest) -> HttpResponse:
        if request.is_mutation or request.method != "GET":
            raise RemoteError("read-only fixture transport refuses mutation", result_unknown=False)
        try:
            return self._responses[(request.method, request.url)]
        except KeyError as exc:
            raise RemoteError("transport fixture has no exact response for requested GET") from exc


def redact(value: str, secrets: tuple[str, ...]) -> str:
    result = value
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    return result
