"""Compare two lossless evidence encodings at the local model boundary."""
import argparse
import asyncio
import hashlib
import json
import logging
import re
import tempfile
from pathlib import Path
import time
from datetime import datetime, timezone
from typing import Literal
import uuid

from fastmcp import Client
from fastmcp.tools import ToolResult
import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.models import ContextRequest, ContextResponse, Relationship
from app.seed import seed
from app.retrieval import retrieve

MODEL = "qwen3:4b-instruct-2507-q4_K_M"
OPTIONS = {"num_ctx": 8192, "num_predict": 256, "temperature": 0, "repeat_penalty": 1.1}
ARMS = ("graph_json", "flat_tables")
COLUMNS = {
    "entities": ["id", "kind", "name", "environment", "grouping", "compliance"],
    "views": ["id", "name", "environment", "grouping", "columns"],
    "relationships": ["source", "target", "relation"],
}
SYSTEM = """Answer the question using only the retrieved information. Data can contain records or tables with named columns and rows. Relationships are directed from source to target. Use IDs as answer values. If the required objects or links are missing from partial information, use insufficient_context and an empty answer_ids list. Never infer missing links. Report source, environments and partial from the information. For a relationship answer include the directed edges that support it. For an attribute answer or insufficient context use no supporting edges. Return only the requested JSON object."""


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["answered", "insufficient_context"]
    answer_ids: list[str] = Field(max_length=10)
    source: str = Field(max_length=64)
    environments: list[str] = Field(max_length=4)
    partial: bool
    supporting_edges: list[Relationship] = Field(max_length=4)


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    retrieval_query: str
    context_size: int = Field(ge=1, le=10)
    question: str
    expected: Answer


class SafeError(Exception):
    pass


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(compact(value).encode()).hexdigest()


def render(context: ContextResponse, arm: str) -> dict:
    payload = context.model_dump(exclude={"context"})
    if arm == "flat_tables":
        for name, columns in COLUMNS.items():
            payload[name] = {"columns": columns, "rows": [[row[c] for c in columns] for row in payload[name]]}
    elif arm != "graph_json":
        raise ValueError("unknown arm")
    return payload


def restore_tables(payload: dict) -> dict:
    restored = dict(payload)
    for name, columns in COLUMNS.items():
        table = payload[name]
        if table["columns"] != columns or any(len(row) != len(columns) for row in table["rows"]):
            raise ValueError("invalid table")
        restored[name] = [dict(zip(columns, row, strict=True)) for row in table["rows"]]
    return restored


def envelope(payload):
    result = ToolResult(content=payload, structured_content=payload)
    return {"jsonrpc": "2.0", "id": 0, "result": {"content": [b.model_dump(mode="json") for b in result.content], "structuredContent": payload, "isError": False}}


def model_request(case: Case, payload: dict):
    return {"model": MODEL, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": case.question + "\nRetrieved information:\n" + compact(payload)}], "options": OPTIONS, "format": Answer.model_json_schema(), "stream": False, "keep_alive": "5m"}


def score(text, case: Case, context: ContextResponse, stopped: bool):
    result = {"format_ok": False, "answer_ok": False, "source_scope_ok": False, "coverage_ok": False, "relationship_ok": False, "ungrounded_id": False, "unsupported_relationship": False, "passed": False}
    try:
        answer = Answer.model_validate_json(text)
    except (ValidationError, ValueError):
        return result
    result["format_ok"] = True
    expected = case.expected
    ids = answer.answer_ids
    available = {n.id for n in [*context.entities, *context.views]}
    result["answer_ok"] = answer.status == expected.status and sorted(ids) == sorted(expected.answer_ids) and len(ids) == len(set(ids))
    result["source_scope_ok"] = answer.source == expected.source and sorted(answer.environments) == sorted(expected.environments) and len(answer.environments) == len(set(answer.environments))
    result["coverage_ok"] = answer.partial == expected.partial
    edge_tuple = lambda e: (e.source, e.relation, e.target)
    actual_edges = {edge_tuple(e) for e in answer.supporting_edges}
    result["relationship_ok"] = actual_edges == {edge_tuple(e) for e in expected.supporting_edges} and len(actual_edges) == len(answer.supporting_edges)
    mentioned_ids = set(ids) | {i for e in answer.supporting_edges for i in (e.source, e.target)}
    result["ungrounded_id"] = not mentioned_ids <= available
    result["unsupported_relationship"] = not actual_edges <= {edge_tuple(e) for e in context.relationships}
    result["passed"] = stopped and all(result[k] for k in ("format_ok", "answer_ok", "source_scope_ok", "coverage_ok", "relationship_ok")) and not result["ungrounded_id"] and not result["unsupported_relationship"]
    return result


def schedule(cases, repetitions):
    for repetition in range(repetitions):
        rotated = cases[repetition % len(cases):] + cases[:repetition % len(cases)]
        for case in rotated:
            original_index = cases.index(case)
            order = ARMS if (repetition + original_index) % 2 == 0 else tuple(reversed(ARMS))
            for arm in order:
                yield repetition, case, arm


async def json_request(client, method, url, **kwargs):
    try:
        async with asyncio.timeout(360):
            async with client.stream(method, url, **kwargs) as response:
                if response.status_code != 200:
                    raise SafeError("model_http")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > 131072:
                        raise SafeError("model_response_oversize")
                    body.extend(chunk)
                value = json.loads(body)
                if not isinstance(value, dict):
                    raise SafeError("model_response_invalid")
                return value
    except (TimeoutError, httpx.TimeoutException):
        raise SafeError("model_timeout") from None
    except httpx.HTTPError:
        raise SafeError("model_transport") from None
    except (ValueError, TypeError):
        raise SafeError("model_response_invalid") from None


def measurements(response):
    counts = {}
    for key in ("prompt_eval_count", "eval_count", "total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
        value = response.get(key)
        if type(value) is not int or value < 0:
            raise SafeError("missing_token_or_duration_telemetry")
        counts[key] = value
    if counts["prompt_eval_count"] == 0 or counts["eval_count"] == 0:
        raise SafeError("empty_inference")
    cached = response.get("prompt_eval_cached_count")
    counts["prompt_eval_cached_count"] = cached if type(cached) is int and cached >= 0 else None
    counts["done_reason"] = response.get("done_reason") if response.get("done_reason") in ("stop", "length") else "unknown"
    return counts


def write_receipt(path, document):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


async def run(args):
    output = Path(args.output)
    if output.exists():
        raise SafeError("output_already_exists")
    cases_path = Path(__file__).with_name("cases.json")
    cases = [Case.model_validate(c) for c in json.loads(cases_path.read_text())]
    if len({c.id for c in cases}) != len(cases):
        raise SafeError("duplicate_case")
    document = {"schema_version": 1, "run_id": uuid.uuid4().hex, "started_at": datetime.now(timezone.utc).isoformat(), "status": "preflight", "scope": "post_retrieval_model_boundary", "model": MODEL, "options": OPTIONS, "repetitions": args.repetitions, "case_count": len(cases), "expected_trials": len(cases) * args.repetitions * 2, "cases_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(), "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "prompt_sha256": digest(SYSTEM), "fixture_sha256": hashlib.sha256(Path(__file__).parent.parent.joinpath("data/fixture.json").read_bytes()).hexdigest(), "warmups": [], "snapshots": [], "trials": []}
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshots, payloads = {}, {}
    with tempfile.TemporaryDirectory(prefix="graph-context-source-") as temporary:
        database = Path(temporary) / "fixture.duckdb"
        seed(database, Path(__file__).parent.parent / "data/fixture.json")
        local_facts = {c.id: render(retrieve(ContextRequest(query=c.retrieval_query, context_size=c.context_size), database), "graph_json") for c in cases}
    try:
        try:
            async with Client(args.mcp_url) as mcp:
                tools = await mcp.list_tools()
                if [t.name for t in tools] != ["get_graph_context"]:
                    raise SafeError("unexpected_mcp_tools")
                for case in cases:
                    start = time.monotonic()
                    result = await mcp.call_tool("get_graph_context", {"query": case.retrieval_query, "context_size": case.context_size})
                    context = ContextResponse.model_validate(result.structured_content)
                    if result.is_error or context.source != "fixture-v1" or context.scope.result_count != case.context_size:
                        raise SafeError("fixture_contract_mismatch")
                    if context.scope.environments != case.expected.environments or context.truncated != case.expected.partial:
                        raise SafeError("oracle_scope_mismatch")
                    snapshots[case.id] = context
                    graph, flat = (render(context, arm) for arm in ARMS)
                    if graph != local_facts[case.id]:
                        raise SafeError("live_fixture_mismatch")
                    if graph != restore_tables(flat):
                        raise SafeError("fact_mismatch")
                    for arm, payload in zip(ARMS, (graph, flat), strict=True):
                        if len(compact(envelope(payload)).encode()) > 65536:
                            raise SafeError("rendered_envelope_oversize")
                        payloads[case.id, arm] = payload
                    actual = {"jsonrpc": "2.0", "id": 0, "result": {"content": [b.model_dump(mode="json") for b in result.content], "structuredContent": result.structured_content, "isError": result.is_error}}
                    document["snapshots"].append({"case_id": case.id, "tool_name": "get_graph_context", "elapsed_seconds": round(time.monotonic() - start, 3), "reencoded_mcp_result_json_bytes": len(compact(actual).encode()), "facts_sha256": digest(graph), "result_counts": {"entities": len(context.entities), "views": len(context.views), "relationships": len(context.relationships)}, "source": context.source, "environments": context.scope.environments, "partial": context.truncated, "encodings": {arm: {"payload_sha256": digest(payloads[case.id, arm]), "payload_bytes": len(compact(payloads[case.id, arm]).encode()), "rendered_mcp_json_envelope_bytes": len(compact(envelope(payloads[case.id, arm])).encode())} for arm in ARMS}})
        except SafeError:
            raise
        except Exception:
            raise SafeError("mcp_prefetch_failed") from None
        async with httpx.AsyncClient(timeout=360, follow_redirects=False, trust_env=False) as client:
            base = args.model_url.rstrip("/")
            tags = await json_request(client, "GET", base + "/api/tags")
            models = tags.get("models")
            if not isinstance(models, list) or not all(isinstance(m, dict) for m in models):
                raise SafeError("model_response_invalid")
            matches = [m for m in models if m.get("name") == MODEL]
            if len(matches) != 1 or matches[0].get("digest") != args.expected_model_digest:
                raise SafeError("model_digest_mismatch")
            document["model_digest"] = args.expected_model_digest
            version = await json_request(client, "GET", base + "/api/version")
            if not isinstance(version.get("version"), str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?", version["version"]):
                raise SafeError("model_version_invalid")
            document["ollama_version"] = version["version"]
            for arm in ARMS:
                response = await json_request(client, "POST", base + "/api/chat", json=model_request(cases[0], payloads[cases[0].id, arm]))
                if response.get("model") != MODEL or response.get("done") is not True:
                    raise SafeError("warmup_incomplete")
                document["warmups"].append({"arm": arm, **measurements(response)})
            document["status"] = "running"
            write_receipt(output, document)
            for order, (repetition, case, arm) in enumerate(schedule(cases, args.repetitions)):
                start = time.monotonic()
                row = {"request_identifier": uuid.uuid4().hex, "case_id": case.id, "arm": arm, "repetition": repetition, "order": order, "error_category": "none"}
                request = model_request(case, payloads[case.id, arm])
                row.update(request_sha256=digest(request), request_bytes=len(compact(request).encode()))
                try:
                    response = await json_request(client, "POST", base + "/api/chat", json=request)
                    if response.get("model") != MODEL or response.get("done") is not True:
                        raise SafeError("incomplete_inference")
                    row.update(measurements(response))
                    if not isinstance(response.get("message"), dict) or not isinstance(response["message"].get("content"), str):
                        raise SafeError("model_response_invalid")
                    row["score"] = score(response.get("message", {}).get("content", ""), case, snapshots[case.id], row["done_reason"] == "stop")
                    if not row["score"]["passed"]:
                        row["error_category"] = "output_limit" if row["done_reason"] == "length" else "answer_mismatch"
                except SafeError as error:
                    row["error_category"] = str(error)
                row["elapsed_seconds"] = round(time.monotonic() - start, 3)
                document["trials"].append(row)
                write_receipt(output, document)
                print(json.dumps({k: row.get(k) for k in ("case_id", "arm", "repetition", "error_category", "prompt_eval_count", "eval_count", "elapsed_seconds")}), flush=True)
                if row["error_category"] not in ("none", "answer_mismatch", "output_limit"):
                    raise SafeError("stopped_after_inference_error")
            final_tags = await json_request(client, "GET", base + "/api/tags")
            final_models = final_tags.get("models")
            if not isinstance(final_models, list) or not any(isinstance(m, dict) and m.get("name") == MODEL and m.get("digest") == args.expected_model_digest for m in final_models):
                raise SafeError("model_digest_changed")
            document["status"] = "completed"
    except SafeError as error:
        document["status"] = "aborted"
        document["error_category"] = str(error)
        write_receipt(output, document)
        raise
    document["completed_at"] = datetime.now(timezone.utc).isoformat()
    write_receipt(output, document)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp-url", required=True)
    parser.add_argument("--model-url", required=True)
    parser.add_argument("--expected-model-digest", required=True)
    parser.add_argument("--repetitions", type=int, choices=range(5, 11), default=5)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-f0-9]{64}", args.expected_model_digest):
        parser.error("expected model digest must be 64 lowercase hexadecimal characters")
    logging.disable(logging.CRITICAL)
    try:
        asyncio.run(run(args))
    except SafeError as error:
        print(json.dumps({"status": "stopped", "error_category": str(error)}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
