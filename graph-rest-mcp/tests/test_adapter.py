import asyncio
import json

import httpx
import pytest

from app import adapter
from app.adapter import AdapterError, Settings, fetch_context
from app.models import ContextRequest
from app.retrieval import retrieve


class Bytes(httpx.AsyncByteStream):
    def __init__(self, chunks, delay=0):
        self.chunks = chunks
        self.delay = delay

    async def __aiter__(self):
        for chunk in self.chunks:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield chunk


def upstream(body, status=200, headers=None, delay=0):
    return httpx.MockTransport(lambda request: httpx.Response(status, headers={"content-type": "application/json", **(headers or {})}, stream=Bytes([body], delay)))


@pytest.mark.asyncio
@pytest.mark.parametrize("status,headers,body,category", [
    (302, {"location": "https://unapproved.example/get-context"}, b"", "upstream_status"),
    (401, {}, b"private upstream body", "upstream_status"),
    (200, {"content-type": "text/plain"}, b"private upstream body", "upstream_content_type"),
    (200, {"content-encoding": "gzip"}, b"private upstream body", "upstream_encoding"),
    (200, {}, b"{" , "upstream_schema"),
    (200, {}, b"{}", "upstream_schema"),
    (200, {}, b"x" * 32769, "upstream_oversize"),
    (200, {"content-length": "32769"}, b"x", "upstream_oversize"),
])
async def test_upstream_failures_are_sanitized(status, headers, body, category):
    with pytest.raises(AdapterError) as caught:
        await fetch_context(ContextRequest(query="production graph"), Settings("http://127.0.0.1/get-context"), upstream(body, status, headers))
    assert str(caught.value) == category


@pytest.mark.asyncio
async def test_upstream_schema_rejects_extra_data_and_broken_edges(database):
    original = retrieve(ContextRequest(query="production graph"), database).model_dump()
    for mutation in ({**original, "unapproved": "private value"}, {**original, "relationships": [{"source": "absent", "target": "prod:checkout", "relation": "contains"}]}):
        with pytest.raises(AdapterError, match="^upstream_schema$"):
            await fetch_context(ContextRequest(query="production graph"), Settings("http://127.0.0.1/get-context"), upstream(json.dumps(mutation).encode()))


@pytest.mark.asyncio
async def test_upstream_cannot_exceed_requested_limit(database):
    result = retrieve(ContextRequest(query="production graph"), database)
    with pytest.raises(AdapterError, match="^upstream_schema$"):
        await fetch_context(ContextRequest(query="production graph", context_size=1), Settings("http://127.0.0.1/get-context"), upstream(result.model_dump_json().encode()))


@pytest.mark.asyncio
async def test_total_timeout(monkeypatch):
    monkeypatch.setattr(adapter, "TOTAL_TIMEOUT_SECONDS", 0.02)
    with pytest.raises(AdapterError, match="^upstream_timeout$"):
        await fetch_context(ContextRequest(query="production graph"), Settings("http://127.0.0.1/get-context"), upstream(b"{}", delay=0.1))


@pytest.mark.parametrize("mode,url", [
    ("local", "https://private.example/get-context"),
    ("local", "http://unapproved.example/get-context"),
    ("remote", "http://private.example/get-context"),
    ("remote", "https://user:password@example.com/get-context"),
    ("remote", "https://example.com/get-context?token=private"),
    ("remote", "https://example.com/other"),
    ("unknown", "https://example.com/get-context"),
])
def test_configuration_boundary(monkeypatch, mode, url):
    monkeypatch.setenv("GRAPH_SERVICE_MODE", mode)
    monkeypatch.setenv("GRAPH_REST_URL", url)
    with pytest.raises(AdapterError, match="^invalid_configuration$"):
        Settings.from_env()


def test_remote_explicit_configuration(monkeypatch):
    monkeypatch.setenv("GRAPH_SERVICE_MODE", "remote")
    monkeypatch.setenv("GRAPH_REST_URL", "https://approved.example/get-context")
    monkeypatch.delenv("GRAPH_AUTH_TOKEN_FILE", raising=False)
    monkeypatch.setenv("GRAPH_EXPECTED_SOURCE", "approved-graph-v1")
    assert Settings.from_env().url == "https://approved.example/get-context"


@pytest.mark.asyncio
async def test_upstream_source_must_match_approved_configuration(database):
    original = retrieve(ContextRequest(query="production graph"), database).model_dump()
    original["source"] = "wrong-graph"
    with pytest.raises(AdapterError, match="^upstream_source$"):
        await fetch_context(ContextRequest(query="production graph"), Settings("http://127.0.0.1/get-context"), upstream(json.dumps(original).encode()))


def test_remote_requires_explicit_source(monkeypatch):
    monkeypatch.setenv("GRAPH_SERVICE_MODE", "remote")
    monkeypatch.setenv("GRAPH_REST_URL", "https://approved.example/get-context")
    monkeypatch.delenv("GRAPH_EXPECTED_SOURCE", raising=False)
    with pytest.raises(AdapterError, match="^invalid_configuration$"):
        Settings.from_env()


def test_remote_custom_path_without_auth(monkeypatch):
    monkeypatch.setenv("GRAPH_SERVICE_MODE", "remote")
    monkeypatch.setenv("GRAPH_REST_PATH", "/get_context/get_context")
    monkeypatch.setenv("GRAPH_REST_URL", "https://approved.example/get_context/get_context")
    monkeypatch.setenv("GRAPH_EXPECTED_SOURCE", "approved-graph-v1")
    monkeypatch.delenv("GRAPH_AUTH_TOKEN_FILE", raising=False)
    monkeypatch.delenv("GRAPH_CA_CERT_FILE", raising=False)
    settings = Settings.from_env()
    assert settings.url.endswith("/get_context/get_context")
    assert settings.auth_file is None


@pytest.mark.parametrize("url,path", [
    ("https://approved.example/get_context/get_context", "/get-context"),
    ("https://approved.example/a//b", "/a//b"),
    ("https://approved.example/a/../b", "/a/../b"),
    ("https://approved.example:bad/get-context", "/get-context"),
    ("https://[broken/get-context", "/get-context"),
])
def test_invalid_remote_paths_and_urls_are_sanitized(monkeypatch, url, path):
    monkeypatch.setenv("GRAPH_SERVICE_MODE", "remote")
    monkeypatch.setenv("GRAPH_REST_URL", url)
    monkeypatch.setenv("GRAPH_REST_PATH", path)
    monkeypatch.setenv("GRAPH_EXPECTED_SOURCE", "approved-graph-v1")
    with pytest.raises(AdapterError, match="^invalid_configuration$"):
        Settings.from_env()


@pytest.mark.asyncio
async def test_remote_request_preserves_method_path_body_and_omits_auth(database):
    result = retrieve(ContextRequest(query="production graph", context_size=3), database)
    def respond(request):
        assert request.method == "POST"
        assert request.url.path == "/get_context/get_context"
        assert "authorization" not in request.headers
        assert json.loads(request.content) == {"query": "production graph", "context_size": 3}
        return httpx.Response(200, headers={"content-type": "application/json"}, stream=Bytes([result.model_dump_json().encode()]))
    actual = await fetch_context(ContextRequest(query="production graph", context_size=3), Settings("https://approved.example/get_context/get_context"), httpx.MockTransport(respond))
    assert actual.scope.result_count == 3


@pytest.mark.asyncio
async def test_private_ca_configuration_failure_is_sanitized(tmp_path):
    invalid_ca = tmp_path / "ca.pem"
    invalid_ca.write_text("not a CA certificate")
    with pytest.raises(AdapterError, match="^tls_configuration$"):
        await fetch_context(ContextRequest(query="production graph"), Settings("https://approved.example/get-context", ca_cert_file=str(invalid_ca)))
