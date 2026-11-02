"""Fixed configuration, durable journal and bounded verified HTTP transports."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import ssl
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener
import uuid

MAX_INPUT = 65536
MAX_OUTPUT = 8192
MAX_UPSTREAM = 262144
HEALTHY_PATTERN = "docker.io/library/*"
FAULTY_PATTERN = "docker.io/libary/*"
CAUSE = "known_good_admission_policy_regression"


class Rejected(ValueError):
    """A deliberate fail-closed boundary; messages contain no upstream payloads."""


class APIError(Rejected):
    def __init__(self, system, status=0):
        self.status = status
        super().__init__(f"{system} request failed (HTTP {status or 'unavailable'})")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def exact(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) <= set(required) | set(optional):
        raise Rejected("Unexpected or missing fields")
    return value


def ident(value, maximum=128):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0," + str(maximum - 1) + r"}", value):
        raise Rejected("Invalid identifier")
    return value


def hash_value(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise Rejected("Invalid SHA256")
    return value


def git_sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value):
        raise Rejected("Invalid Git revision")
    return value


def integer(value, minimum=0, maximum=2**53 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise Rejected("Invalid integer")
    return value


def endpoint(value, schemes=("https",)):
    if not isinstance(value, str):
        raise Rejected("Invalid configured endpoint")
    p = urlsplit(value)
    if (p.scheme not in schemes or not p.hostname or p.username or p.password or p.query or p.fragment
            or any(c in value for c in "\r\n\t")):
        raise Rejected("Invalid configured endpoint")
    return value.rstrip("/")


POLICY_OBSERVATION_METHOD = "stable-read-and-admission-probes"


def validate_policy_bracket(before, after, uid, generation, spec_hash, probe_times, now, max_age):
    """Validate an explicit active-admission proof; never synthesize status fields."""
    for value in (before, after):
        exact(value, ("uid", "generation", "policy_spec_sha256", "ready", "deleting", "enforcement", "observed_at"))
        ident(value["uid"])
        integer(value["generation"], 1)
        hash_value(value["policy_spec_sha256"])
        integer(value["observed_at"], 1)
        if (value["uid"] != uid or value["generation"] != generation or value["policy_spec_sha256"] != spec_hash
                or value["ready"] is not True or value["deleting"] is not False or value["enforcement"] != "Enforce"
                or not now - max_age <= value["observed_at"] <= now):
            raise Rejected("Policy bracket does not prove the current ready enforced generation")
    if not probe_times or not before["observed_at"] <= min(probe_times) <= max(probe_times) <= after["observed_at"]:
        raise Rejected("Actual admission observations must be bracketed by stable policy reads")


class Phase(str, Enum):
    OBSERVING = "observing"
    CANDIDATE = "candidate"
    CLASSIFIED = "classified"
    DISPATCH_PENDING = "dispatch_pending"
    DISPATCH_UNKNOWN = "dispatch_unknown"
    INVESTIGATING = "investigating"
    PROPOSED = "proposed"
    REVIEWED = "reviewed"
    AWAITING_HUMAN = "awaiting_human"
    AUTHORIZED = "authorized"
    MERGE_UNKNOWN = "merge_unknown"
    RECONCILING = "reconciling"
    VERIFIED = "verified"


@dataclass(frozen=True)
class Config:
    run_id: str
    incident_id: str
    profile_revision: str
    cluster_id: str
    namespace: str
    policy_name: str
    rule_name: str
    application: str
    gitlab_api: str
    project_id: str
    policy_file: str
    target_branch: str
    fix_branch: str
    faulty_policy_sha256: str
    faulty_policy_spec_sha256: str
    healthy_policy_sha256: str
    healthy_policy_spec_sha256: str
    flux_namespace: str
    flux_source: str
    flux_kustomization: str
    application_url: str
    expected_body_sha256: str
    investigator_id: str
    reviewer_id: str
    human_approver_id: str
    required_ci_jobs: tuple
    required_test_cases: tuple
    otlp_endpoint: str = ""
    kubernetes_api: str = "https://kubernetes.default.svc"
    expected_http_status: int = 200
    evidence_max_age_seconds: int = 300
    kubernetes_service: str = "kyverno-kubernetes-mcp"
    gitlab_service: str = "kyverno-gitlab-mcp"
    schema_version: int = 1

    @classmethod
    def from_dict(cls, value):
        allowed = {f.name for f in fields(cls)}
        if not isinstance(value, dict) or set(value) - allowed:
            raise Rejected("Unexpected configuration fields")
        try:
            v = dict(value)
            for key in ("required_ci_jobs", "required_test_cases"):
                if not isinstance(v[key], (list, tuple)) or not 1 <= len(v[key]) <= 8 or len(set(v[key])) != len(v[key]):
                    raise Rejected("Explicit distinct CI jobs and admission test cases are required")
                v[key] = tuple(ident(item) for item in v[key])
            c = cls(**v)
        except (KeyError, TypeError):
            raise Rejected("Missing configuration fields") from None
        for key in ("run_id", "incident_id", "cluster_id", "investigator_id", "reviewer_id", "human_approver_id", "kubernetes_service", "gitlab_service"):
            ident(getattr(c, key))
        for key in ("namespace", "policy_name", "rule_name", "application", "flux_namespace", "flux_source", "flux_kustomization"):
            if not isinstance(getattr(c, key), str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,252}", getattr(c, key)):
                raise Rejected("Invalid configured Kubernetes name")
        if len({c.investigator_id, c.reviewer_id, c.human_approver_id}) != 3:
            raise Rejected("Investigator, reviewer and human must be distinct")
        for key in ("profile_revision", "faulty_policy_sha256", "faulty_policy_spec_sha256", "healthy_policy_sha256", "healthy_policy_spec_sha256", "expected_body_sha256"):
            hash_value(getattr(c, key))
        if c.faulty_policy_sha256 == c.healthy_policy_sha256:
            raise Rejected("Faulty and healthy policy hashes must differ")
        if not isinstance(c.project_id, str) or not re.fullmatch(r"[1-9][0-9]{0,15}", c.project_id):
            raise Rejected("Require the exact numeric GitLab project ID")
        if (not isinstance(c.policy_file, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,255}\.json", c.policy_file)
                or any(p in {"", ".", ".."} for p in c.policy_file.split("/"))):
            raise Rejected("Require a scoped JSON policy file")
        for branch in (c.target_branch, c.fix_branch):
            if not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}", branch) or ".." in branch or "//" in branch or branch.endswith(("/", ".", ".lock")):
                raise Rejected("Invalid fixed branch")
        if c.target_branch == c.fix_branch:
            raise Rejected("Fix branch must differ from the target")
        endpoint(c.gitlab_api)
        endpoint(c.kubernetes_api)
        endpoint(c.application_url, ("http", "https"))
        if c.otlp_endpoint:
            endpoint(c.otlp_endpoint, ("http", "https"))
        integer(c.expected_http_status, 200, 299)
        integer(c.evidence_max_age_seconds, 30, 300)
        if type(c.schema_version) is not int or c.schema_version != 1:
            raise Rejected("Unsupported configuration version")
        return c

    @property
    def identity(self):
        return digest(asdict(self))

    @property
    def fingerprint(self):
        # Deliberately excludes pod names, timestamps, Git revisions and run IDs.
        return digest([self.cluster_id, self.namespace, self.application, self.policy_name, self.rule_name, CAUSE])


class Ledger:
    def __init__(self, path, identity):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
            intent TEXT NOT NULL, receipt TEXT, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, value TEXT NOT NULL, observed_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY, value TEXT NOT NULL, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS classifications(candidate_id TEXT PRIMARY KEY, ordinal INTEGER UNIQUE NOT NULL,
            status TEXT NOT NULL, value TEXT, reserved_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY CHECK(id=1), message_id TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS counters(key TEXT PRIMARY KEY, value INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS receipt_identities(id TEXT PRIMARY KEY, payload_hash TEXT NOT NULL);
        """)
        with self.transaction() as db:
            row = db.execute("SELECT value FROM metadata WHERE key='config_identity'").fetchone()
            if row and row["value"] != identity:
                raise Rejected("Database is bound to a different immutable configuration")
            db.execute("INSERT OR IGNORE INTO metadata VALUES('config_identity',?)", (identity,))
            db.execute("INSERT OR IGNORE INTO state VALUES(1,?)", (canonical({"phase": Phase.OBSERVING.value}).decode(),))

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            else:
                self.db.execute("COMMIT")

    def state(self, db=None):
        with self.lock:
            return json.loads((db or self.db).execute("SELECT value FROM state WHERE id=1").fetchone()["value"])

    def patch(self, patch, db=None):
        if db is None:
            with self.transaction() as tx:
                return self.patch(patch, tx)
        value = {**self.state(db), **patch}
        db.execute("UPDATE state SET value=? WHERE id=1", (canonical(value).decode(),))
        return value

    def count(self, key):
        with self.transaction() as db:
            db.execute("INSERT INTO counters VALUES(?,1) ON CONFLICT(key) DO UPDATE SET value=value+1", (key,))

    def operation(self, op_id):
        with self.lock:
            row = self.db.execute("SELECT * FROM operations WHERE id=?", (op_id,)).fetchone()
            if row:
                return {**dict(row), "intent": json.loads(row["intent"]), "receipt": json.loads(row["receipt"]) if row["receipt"] else None}
        return None

    def reserve_operation(self, op_id, kind, intent):
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM operations WHERE id=?", (op_id,)).fetchone():
                return False
            db.execute("INSERT INTO operations VALUES(?,?,?, ?,NULL,?)", (op_id, kind, "unknown", canonical(intent).decode(), int(time.time())))
        return True

    def resolve_operation(self, op_id, receipt):
        with self.transaction() as db:
            db.execute("UPDATE operations SET status='confirmed',receipt=? WHERE id=?", (canonical(receipt).decode(), op_id))

    def close(self):
        with self.lock:
            self.db.close()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


class HTTPJSON:
    def __init__(self, system, base, token_file=None, ca_file=None, read_only=False):
        self.system, self.base = system, endpoint(base)
        self.token_file, self.read_only = token_file, read_only
        ctx = ssl.create_default_context(cafile=ca_file)
        self.opener = build_opener(NoRedirect(), HTTPSHandler(context=ctx))

    def request(self, path, method="GET", body=None, traceparent=None):
        if not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or "\r" in path or "\n" in path:
            raise Rejected("Invalid internal API path")
        if self.read_only and (method != "GET" or body is not None):
            raise Rejected("Kubernetes adapter permits GET only")
        headers = {"Accept": "application/json"}
        if self.token_file:
            try:
                token = Path(self.token_file).read_text().strip()
            except OSError:
                raise APIError(self.system) from None
            if not token or any(c in token for c in "\r\n"):
                raise APIError(self.system)
            headers["Authorization"] = "Bearer " + token
        if traceparent:
            headers["traceparent"] = traceparent
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = Request(self.base + path, canonical(body) if body is not None else None, headers, method=method)
        try:
            with self.opener.open(req, timeout=15) as response:
                raw = response.read(MAX_UPSTREAM + 1)
            if len(raw) > MAX_UPSTREAM:
                raise Rejected("Upstream response exceeds transport limit")
            return json.loads(raw)
        except HTTPError as error:
            error.close()
            raise APIError(self.system, error.code) from None
        except (URLError, OSError, ValueError):
            raise APIError(self.system) from None


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    parent_id: str = ""
    tool_call_id: str = ""
    task_id: str = ""

    @classmethod
    def incoming(cls, carrier="", metadata=None):
        match = re.fullmatch(r"00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}", carrier)
        valid = match and int(match[1], 16) and int(match[2], 16)
        meta = metadata if isinstance(metadata, dict) else {}
        def safe(*keys):
            for key in keys:
                item = meta.get(key)
                if isinstance(item, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", item):
                    return item
            return ""
        return cls(match[1] if valid else uuid.uuid4().hex, match[2] if valid else "",
                   safe("tool_call_id", "toolCallId", "mcp.tool.call.id"), safe("task_id", "taskId", "a2a.task.id"))


class Telemetry:
    def __init__(self, config, ledger):
        self.config, self.ledger = config, ledger
        self.opener = build_opener(NoRedirect())

    def export(self, service, context, span, name, started, error=False, values=None):
        attrs = {"flow.component": "mcp", "flow.simulated": False, "flow.incident.id": self.config.incident_id,
                 "flow.run.id": self.config.run_id, **(values or {})}
        if context.tool_call_id:
            attrs["gen_ai.tool.call.id"] = context.tool_call_id
            attrs["mcp.tool.call.id"] = context.tool_call_id
        if context.task_id:
            attrs["a2a.task.id"] = context.task_id
        attributes = [{"key": k, "value": {"boolValue": v} if isinstance(v, bool) else
                       {"intValue": str(v)} if type(v) is int else {"stringValue": str(v)}} for k, v in attrs.items()]
        resource = {"attributes": [{"key": "service.name", "value": {"stringValue": service}}]}
        end = str(time.time_ns())
        span_value = {"traceId": context.trace_id, "spanId": span, "name": name, "kind": 2,
                      "startTimeUnixNano": str(started), "endTimeUnixNano": end,
                      "status": {"code": 2 if error else 1}, "attributes": attributes}
        if context.parent_id:
            span_value["parentSpanId"] = context.parent_id
        payloads = {
            "traces": {"resourceSpans": [{"resource": resource, "scopeSpans": [{"spans": [span_value]}]}]},
            "logs": {"resourceLogs": [{"resource": resource, "scopeLogs": [{"logRecords": [{
                "timeUnixNano": end, "traceId": context.trace_id, "spanId": span,
                "severityNumber": 17 if error else 9, "eventName": "kyverno.mcp.operation", "attributes": attributes}]}]}]},
        }
        delivered = bool(self.config.otlp_endpoint)
        if delivered:
            for signal, payload in payloads.items():
                try:
                    req = Request(self.config.otlp_endpoint.rstrip("/") + "/v1/" + signal, canonical(payload), {"Content-Type": "application/json"})
                    with self.opener.open(req, timeout=3) as response:
                        response.read(1024)
                except OSError:
                    delivered = False
        self.ledger.count("telemetry_export_success" if delivered else "telemetry_export_failed")
        self.ledger.patch({"last_tool_telemetry": {"trace_id": context.trace_id, "span_id": span, "service": service,
                                                  "tool": attrs.get("gen_ai.tool.name", ""), "exported": delivered}})
        return delivered
