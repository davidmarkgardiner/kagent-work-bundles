import asyncio
import json
import os
import re
import ssl
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from app.models import ContextRequest, ContextResponse


MAX_UPSTREAM_BYTES = 32768
TOTAL_TIMEOUT_SECONDS = 5.0


class AdapterError(Exception):
    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


@dataclass(frozen=True)
class Settings:
    url: str
    auth_file: str | None = None
    expected_source: str = "fixture-v1"
    ca_cert_file: str | None = None

    @classmethod
    def from_env(cls):
        url = os.getenv("GRAPH_REST_URL", "http://graph-rest:8001/get-context")
        mode = os.getenv("GRAPH_SERVICE_MODE", "local")
        path = os.getenv("GRAPH_REST_PATH", "/get-context")
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            raise AdapterError("invalid_configuration") from None
        if not re.fullmatch(r"/[a-zA-Z0-9_/-]+", path) or "//" in path:
            raise AdapterError("invalid_configuration")
        if mode not in {"local", "remote"} or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path != path or not parsed.hostname or port == 0:
            raise AdapterError("invalid_configuration")
        if mode == "remote" and parsed.scheme != "https":
            raise AdapterError("invalid_configuration")
        if mode == "local" and (parsed.scheme != "http" or parsed.hostname not in {"graph-rest", "graph-rest.graph-context-lab.svc.cluster.local", "localhost", "127.0.0.1"}):
            raise AdapterError("invalid_configuration")
        auth_file = os.getenv("GRAPH_AUTH_TOKEN_FILE")
        ca_cert_file = os.getenv("GRAPH_CA_CERT_FILE")
        if mode == "local" and (auth_file or ca_cert_file or path != "/get-context"):
            raise AdapterError("invalid_configuration")
        expected_source = "fixture-v1" if mode == "local" else os.getenv("GRAPH_EXPECTED_SOURCE", "")
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,64}", expected_source):
            raise AdapterError("invalid_configuration")
        return cls(url, auth_file, expected_source, ca_cert_file)


async def fetch_context(request: ContextRequest, settings: Settings | None = None, transport=None) -> ContextResponse:
    settings = settings or Settings.from_env()
    headers = {"Accept": "application/json", "Accept-Encoding": "identity"}
    verify = True
    if settings.ca_cert_file:
        try:
            verify = ssl.create_default_context(cafile=settings.ca_cert_file)
        except (OSError, ssl.SSLError):
            raise AdapterError("tls_configuration") from None
    if settings.auth_file:
        try:
            token = Path(settings.auth_file).read_text().strip()
        except (OSError, UnicodeError):
            raise AdapterError("authentication_unavailable") from None
        if not token or not token.isascii() or len(token) > 4096 or any(char.isspace() for char in token):
            raise AdapterError("authentication_unavailable")
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with asyncio.timeout(TOTAL_TIMEOUT_SECONDS):
            async with httpx.AsyncClient(timeout=TOTAL_TIMEOUT_SECONDS, follow_redirects=False, trust_env=False, verify=verify, transport=transport) as client:
                async with client.stream("POST", settings.url, json=request.model_dump(), headers=headers) as response:
                    if response.status_code != 200:
                        raise AdapterError("upstream_status")
                    if response.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
                        raise AdapterError("upstream_content_type")
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise AdapterError("upstream_encoding")
                    content_length = response.headers.get("content-length")
                    if content_length and (not content_length.isdigit() or int(content_length) > MAX_UPSTREAM_BYTES):
                        raise AdapterError("upstream_oversize")
                    body = bytearray()
                    async for chunk in response.aiter_raw():
                        if len(body) + len(chunk) > MAX_UPSTREAM_BYTES:
                            raise AdapterError("upstream_oversize")
                        body.extend(chunk)
                    result = ContextResponse.model_validate_json(body)
                    if result.source != settings.expected_source:
                        raise AdapterError("upstream_source")
                    if result.scope.result_count > request.context_size:
                        raise AdapterError("upstream_schema")
                    return result
    except (asyncio.TimeoutError, httpx.TimeoutException):
        raise AdapterError("upstream_timeout") from None
    except (ValidationError, ValueError, json.JSONDecodeError):
        raise AdapterError("upstream_schema") from None
    except httpx.HTTPError:
        raise AdapterError("upstream_transport") from None
