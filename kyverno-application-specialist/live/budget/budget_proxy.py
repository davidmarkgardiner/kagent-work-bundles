#!/usr/bin/env python3
"""Fixed-destination, durable request-budget proxy. Python standard library only."""
import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import fcntl
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
import re
import socket
import sqlite3
import threading
from urllib.parse import urlsplit

REQUEST_LIMIT = 65536
RESPONSE_LIMIT = 1048576
UPSTREAM_TIMEOUT = 100
FIELDS = {"model", "messages", "tools", "tool_choice", "temperature", "max_tokens",
          "stream", "parallel_tool_calls", "response_format", "store", "reasoning_effort"}


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    def constant(_):
        raise ValueError("non-finite number")
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("non-finite number")
        if isinstance(value, dict):
            for child in value.values():
                finite(child)
        elif isinstance(value, list):
            for child in value:
                finite(child)
    finite(result)
    return result


@dataclass(frozen=True)
class Config:
    upstream_base_url: str
    model: str
    run_id: str
    max_requests: int
    max_input_bytes: int
    max_output_tokens: int

    @classmethod
    def read(cls, path):
        with open(path, "rb") as handle:
            raw = handle.read(REQUEST_LIMIT + 1)
            if len(raw) > REQUEST_LIMIT:
                raise ValueError("configuration too large")
            value = strict_json(raw)
        if not isinstance(value, dict) or set(value) != set(cls.__annotations__):
            raise ValueError("configuration fields must match documented schema")
        config = cls(**value)
        for name, ceiling in (("max_requests", 32), ("max_input_bytes", 524288),
                              ("max_output_tokens", 1200)):
            amount = getattr(config, name)
            if type(amount) is not int or not 1 <= amount <= ceiling:
                raise ValueError("configuration ceiling invalid")
        for name in ("model", "run_id"):
            item = getattr(config, name)
            if not isinstance(item, str) or not item.strip() or len(item) > 256:
                raise ValueError("configuration identity invalid")
        if not isinstance(config.upstream_base_url, str):
            raise ValueError("upstream URL invalid")
        url = urlsplit(config.upstream_base_url)
        if (url.scheme not in ("https", "http") or not url.hostname or
                url.username is not None or url.password is not None or
                url.path not in ("", "/") or url.query or url.fragment or
                any(c.isspace() or ord(c) < 32 for c in config.upstream_base_url)):
            raise ValueError("upstream URL invalid")
        if url.scheme == "http" and not url.hostname.endswith((".svc", ".svc.cluster.local")):
            raise ValueError("HTTP upstream must be a Kubernetes service DNS name")
        if url.port is not None and not 1 <= url.port <= 65535:
            raise ValueError("upstream port invalid")
        return config

    def digest(self):
        value = json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(value.encode()).hexdigest()


class BudgetStore:
    def __init__(self, path, config):
        self.path, self.config = path, config
        with self.connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS identity (singleton INTEGER PRIMARY KEY CHECK(singleton=1), digest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY, input_bytes INTEGER NOT NULL,
                    digest TEXT, status TEXT NOT NULL, http_status INTEGER, usage TEXT);
            """)
            conn.execute("BEGIN IMMEDIATE")
            identity = conn.execute("SELECT digest FROM identity WHERE singleton=1").fetchone()
            if identity and identity[0] != config.digest():
                raise ValueError("existing budget configuration mismatch")
            conn.execute("INSERT OR IGNORE INTO identity VALUES (1, ?)", (config.digest(),))
            conn.execute("UPDATE attempts SET status='interrupted' WHERE status='pending'")

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.execute("PRAGMA busy_timeout=10000")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def reserve(self, planned_bytes):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            count, used = conn.execute("SELECT COUNT(*), COALESCE(SUM(input_bytes),0) FROM attempts").fetchone()
            if count >= self.config.max_requests:
                return None, "request_budget_exhausted"
            reason = None
            charge = planned_bytes
            if charge > self.config.max_input_bytes - used:
                charge, reason = 0, "input_budget_exhausted"
            attempt = conn.execute("INSERT INTO attempts(input_bytes,status) VALUES (?, 'pending')", (charge,)).lastrowid
            return attempt, reason

    def finish(self, attempt, category, status, digest=None, usage=None):
        with self.connection() as conn:
            # An attempt can finish once. Byte reservations are never refunded.
            conn.execute("""UPDATE attempts SET status=?, http_status=?, digest=?, usage=?
                         WHERE id=? AND status='pending'""",
                         (category, status, digest, json.dumps(usage) if usage else None, attempt))

    def summary(self):
        with self.connection() as conn:
            count, used = conn.execute("SELECT COUNT(*), COALESCE(SUM(input_bytes),0) FROM attempts").fetchone()
            statuses = dict(conn.execute("SELECT status,COUNT(*) FROM attempts GROUP BY status"))
        return {"requests_reserved": count, "input_bytes": used,
                "requests_remaining": max(0, self.config.max_requests-count),
                "input_bytes_remaining": max(0, self.config.max_input_bytes-used),
                "statuses": statuses}


def numeric_usage(value):
    """Keep actual numeric provider counters only; never provider strings/content."""
    if not isinstance(value, dict):
        return None
    result = {}
    allowed = {"prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens"}
    details = {"prompt_tokens_details", "completion_tokens_details", "input_tokens_details", "output_tokens_details"}
    detail_keys = {"cached_tokens", "audio_tokens", "reasoning_tokens", "accepted_prediction_tokens", "rejected_prediction_tokens"}
    for key in allowed:
        number = value.get(key)
        if type(number) in (int, float) and (type(number) is int or math.isfinite(number)) and number >= 0:
            result[key] = number
    for key in details:
        if isinstance(value.get(key), dict):
            counters = {k: v for k, v in value[key].items() if k in detail_keys and
                        type(v) in (int, float) and (type(v) is int or math.isfinite(v)) and v >= 0}
            if counters:
                result[key] = counters
    return result or None


def forward(config, payload, headers):
    url = urlsplit(config.upstream_base_url)
    cls = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
    conn = cls(url.hostname, url.port, timeout=UPSTREAM_TIMEOUT)
    expired = threading.Event()
    connected_socket = [None]
    result = None
    def abort():
        expired.set()
        sock = connected_socket[0] or conn.sock
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        conn.close()
    timer = threading.Timer(UPSTREAM_TIMEOUT, abort)
    timer.daemon = True
    timer.start()
    try:
        conn.request("POST", "/v1/chat/completions", body=payload, headers=headers)
        connected_socket[0] = conn.sock
        result = conn.getresponse()
        body = result.read(RESPONSE_LIMIT + 1)
        if expired.is_set():
            raise TimeoutError()
        return result.status, body
    except Exception:
        if expired.is_set():
            raise TimeoutError() from None
        raise
    finally:
        timer.cancel()
        if result is not None:
            result.close()
        conn.close()


def validated_payload(raw, config):
    value = strict_json(raw)
    if not isinstance(value, dict) or set(value) - FIELDS:
        raise ValueError()
    if value.get("model", config.model) != config.model:
        raise ValueError()
    if value.get("stream", False) is not False:
        raise ValueError()
    tokens = value.get("max_tokens", config.max_output_tokens)
    if type(tokens) is not int or not 1 <= tokens <= config.max_output_tokens:
        raise ValueError()
    if not isinstance(value.get("messages"), list) or not value["messages"] or not all(isinstance(m, dict) for m in value["messages"]):
        raise ValueError()
    for field in ("parallel_tool_calls", "store"):
        if field in value and type(value[field]) is not bool:
            raise ValueError()
    if "temperature" in value and (type(value["temperature"]) not in (int, float) or not 0 <= value["temperature"] <= 2):
        raise ValueError()
    if "reasoning_effort" in value and value["reasoning_effort"] != "low":
        raise ValueError()
    if "tools" in value and not isinstance(value["tools"], list):
        raise ValueError()
    if "response_format" in value and not isinstance(value["response_format"], dict):
        raise ValueError()
    value.update(model=config.model, stream=False, max_tokens=tokens)
    return json.dumps(value, allow_nan=False, separators=(",", ":")).encode()


def valid_traceparent(value):
    # W3C version 00 has no extensions. Future versions require a valid base prefix.
    match = re.fullmatch(r"([0-9a-f]{2})-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})(-[\x21-\x7e]+)?", value)
    return bool(match and match[1] != "ff" and int(match[2], 16) and int(match[3], 16)
                and (match[1] != "00" or match[5] is None))


class Handler(BaseHTTPRequestHandler):
    server_version = "BudgetProxy"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(UPSTREAM_TIMEOUT)

    def reply(self, status, body):
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def error(self, status, code):
        self.reply(status, json.dumps({"error": {"message": code, "type": "budget_proxy_error", "code": code}}).encode())

    def do_GET(self):
        if self.path != "/healthz":
            self.error(404, "route_not_found")
            return
        self.reply(200, json.dumps(self.server.store.summary()).encode())

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.error(404, "route_not_found")
            return
        lengths = self.headers.get_all("Content-Length", [])
        framing_ok = len(lengths) == 1 and re.fullmatch(r"[0-9]+", lengths[0]) is not None and not self.headers.get_all("Transfer-Encoding")
        length = int(lengths[0]) if framing_ok and len(lengths[0]) <= 10 else 0
        framing_ok = framing_ok and len(lengths[0]) <= 10
        planned = length if framing_ok and length <= REQUEST_LIMIT else 0
        try:
            attempt, reason = self.server.store.reserve(planned)
        except sqlite3.Error:
            self.error(503, "budget_store_unavailable")
            return
        if attempt is None:
            self.error(429, reason)
            return
        raw = b""
        digest = None
        finished = False
        def fail(status, code):
            nonlocal finished
            try:
                self.server.store.finish(attempt, code, status, digest)
            except sqlite3.Error:
                status, code = 503, "budget_store_unavailable"
            finished = True
            self.error(status, code)
        try:
            if reason:
                fail(429, reason)
                return
            if not framing_ok:
                fail(400, "invalid_request_framing")
                return
            if length > REQUEST_LIMIT:
                fail(413, "request_too_large")
                return
            raw = self.rfile.read(length)
            digest = hashlib.sha256(raw).hexdigest()
            if len(raw) != length:
                fail(400, "incomplete_request_body")
                return
            content_types = self.headers.get_all("Content-Type", [])
            if len(content_types) != 1 or content_types[0].split(";", 1)[0].strip().lower() != "application/json" or self.headers.get_all("Content-Encoding"):
                fail(415, "unsupported_content_type")
                return
            try:
                payload = validated_payload(raw, self.server.config)
            except (ValueError, TypeError, RecursionError, UnicodeError):
                fail(400, "invalid_completion_request")
                return
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            auth = self.headers.get_all("Authorization", [])
            trace = self.headers.get_all("traceparent", [])
            if len(auth) > 1 or any(ord(c) < 32 or ord(c) == 127 for value in auth for c in value):
                fail(400, "invalid_authorization_header")
                return
            if auth:
                headers["Authorization"] = auth[0]
            if len(trace) == 1 and valid_traceparent(trace[0]):
                headers["traceparent"] = trace[0]
            try:
                status, response = self.server.transport(self.server.config, payload, headers)
            except (socket.timeout, TimeoutError):
                fail(504, "upstream_timeout")
                return
            except Exception:
                fail(502, "upstream_transport_error")
                return
            if len(response) > RESPONSE_LIMIT:
                fail(502, "upstream_response_too_large")
                return
            try:
                result = strict_json(response)
                if not isinstance(result, dict) or not 200 <= status <= 599 or 300 <= status <= 399:
                    raise ValueError()
            except (ValueError, TypeError, RecursionError, UnicodeError):
                fail(502, "invalid_upstream_response")
                return
            self.server.store.finish(attempt, "upstream_success" if status < 300 else "upstream_error", status,
                                     digest, numeric_usage(result.get("usage")))
            finished = True
            self.reply(status, response)
        except (socket.timeout, TimeoutError):
            fail(408, "request_body_timeout")
        except (OSError, sqlite3.Error):
            if not finished:
                # No retry and no content-bearing exception details escape.
                try:
                    fail(503, "budget_proxy_failure")
                except OSError:
                    pass
        finally:
            if not finished:
                try:
                    fail(503, "proxy_interrupted")
                except OSError:
                    pass


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 64
    def handle_error(self, *_):
        # Default server traceback can contain request header/body data from exceptions.
        pass

    def server_close(self):
        super().server_close()
        lease = getattr(self, "lease", None)
        if lease is not None:
            os.close(lease)
            self.lease = None


def create_server(config, db_path, host="0.0.0.0", port=8082, transport=forward):
    # One serving process per DB; prevents a second startup from relabeling live attempts.
    lease = os.open(db_path + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        store = BudgetStore(db_path, config)
        server = Server((host, port), Handler)
        server.lease = lease
        server.config, server.store, server.transport = config, store, transport
        return server
    except Exception:
        os.close(lease)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/config/budget.json")
    parser.add_argument("--db", default="/data/model-budget.sqlite")
    args = parser.parse_args()
    try:
        config = Config.read(args.config)
        server = create_server(config, args.db, os.environ.get("HOST", "0.0.0.0"), int(os.environ.get("PORT", "8082")))
    except Exception:
        raise SystemExit("budget proxy startup refused: configuration, database or bind invalid") from None
    server.serve_forever()


if __name__ == "__main__":
    main()
