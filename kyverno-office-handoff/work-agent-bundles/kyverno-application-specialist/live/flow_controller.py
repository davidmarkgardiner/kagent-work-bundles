"""Durable local demo sequencing. Network effects belong to the trusted adapter."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import threading
import time
import uuid


STEPS = ("prepare", "inject_fault", "observe_fault", "classify", "dispatch", "triage",
         "review", "await_approval", "merge", "observe_merge", "await_recovery", "measure_recovery", "verify", "close")
STEP_PHASE = dict(zip(STEPS, ("preparing", "preparing", "observing", "classifying", "dispatching",
                             "triaging", "waiting_review", "waiting_human", "merging", "merging", "reconciling", "reconciling", "verifying", "closing_ticket")))
NEXT_STEP = dict(zip(STEPS, STEPS[1:])) | {"recheck_fault": "classify", "classification_followup": "dispatch", "triage_continuation": "review"}
STEP_PHASE["recheck_fault"] = "observing"
STEP_PHASE["classification_followup"] = "classifying"
STEP_PHASE["triage_continuation"] = "triaging"
READ_ONLY_STEPS = frozenset({"recheck_fault", "observe_fault", "triage", "await_approval", "observe_merge", "await_recovery"})
PENDING_PHASES = {**{step: {phase} for step, phase in STEP_PHASE.items()},
                  "triage": {"triaging", "waiting_ci"}, "triage_continuation": {"triaging", "waiting_ci"}, "observe_fault": {"fault_injected", "observing"}}
STATUSES = frozenset({"completed", "pending", "suppressed", "unknown", "blocked"})
TERMINAL_NATIVE = frozenset({"completed", "COMPLETED", "TASK_STATE_COMPLETED"})
PUBLIC_FIELDS = {
    "ticket": {"iid": None, "url": None, "state": None, "closedVerified": False},
    "classifier": {"decision": None, "severity": None, "confidence": None, "threshold": 0.95, "attempts": None},
    "native": {"agent": None, "taskId": None, "state": None, "traceId": None},
    "remedy": {"summary": None, "mrUrl": None, "headSha": None, "ci": None, "review": None},
    "approval": {"approvalId": None, "headSha": None, "approvedBy": None, "approvedAt": None, "expiresAt": None, "state": None},
    "merge": {"sha": None, "mergedBy": None, "status": None, "taskId": None, "taskState": None, "traceId": None, "approvalId": None},
    "verification": {"taskId": None, "state": None, "checks": [], "traceId": None},
}


class FlowError(ValueError):
    pass


class ResumeConflict(FlowError):
    pass


class ApprovalConflict(FlowError):
    pass


class ApprovalUnknown(FlowError):
    pass


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def merged(previous, patch):
    result = dict(previous)
    for key, value in patch.items():
        result[key] = merged(result.get(key, {}), value) if isinstance(value, dict) and isinstance(result.get(key, {}), dict) else value
    return result


@dataclass(frozen=True)
class StepResult:
    status: str
    patch: dict = field(default_factory=dict)
    events: tuple = ()
    phase: str | None = None
    poll_after: float = 2.0

    @classmethod
    def parse(cls, value):
        result = cls(**value) if isinstance(value, dict) else value
        if (not isinstance(result, cls) or result.status not in STATUSES or not isinstance(result.patch, dict)
                or not isinstance(result.events, (list, tuple)) or len(result.events) > 16
                or type(result.poll_after) not in {int, float} or not math.isfinite(result.poll_after)
                or not 0.01 <= result.poll_after <= 60 or len(encoded(result.patch).encode()) > 65536):
            raise FlowError("Invalid bounded adapter result")
        return result


@dataclass(frozen=True)
class ClosureProof:
    verified: bool = False
    task_id: str | None = None
    task_state: str | None = None
    evidence_digest: str | None = None
    issue_closed: bool = False
    issue_iid: int | None = None


class FlowController:
    """One configured scope and one unresolved run, with no implicit effect retry.

    adapter.advance(run, step) receives run['_call']['mode']. Only its first
    execute call may create or send. Every observe call is read-only.
    """

    def __init__(self, db_path, adapter, scope, run_root=None, config_factory=None,
                 closure_verifier=None, autostart=True, poll_interval=2.0, telemetry=None):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_root = Path(run_root) if run_root else self.path.parent / "runs"
        self.scope = json.loads(encoded(scope))
        if not isinstance(self.scope, dict) or not self.scope:
            raise FlowError("A fixed configured scope is required")
        self.adapter, self.config_factory, self.closure_verifier = adapter, config_factory, closure_verifier
        self.telemetry = telemetry
        self.autostart, self.poll_interval = autostart, poll_interval
        self._stop, self._wake = threading.Event(), threading.Event()
        self._thread, self._mutex, self._advance_mutex = None, threading.RLock(), threading.Lock()
        self._lease = os.open(str(self.path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self._connection() as db:
                db.execute("PRAGMA journal_mode=WAL")
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY,step TEXT NOT NULL,phase TEXT NOT NULL,
                        status TEXT NOT NULL,active INTEGER NOT NULL,config TEXT NOT NULL,data TEXT NOT NULL,
                        created_at REAL NOT NULL,updated_at REAL NOT NULL,next_poll REAL NOT NULL DEFAULT 0);
                    CREATE UNIQUE INDEX IF NOT EXISTS one_active_run ON runs(active) WHERE active=1;
                    CREATE TABLE IF NOT EXISTS requests(request_id TEXT PRIMARY KEY,run_id TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS intents(run_id TEXT NOT NULL,step TEXT NOT NULL,intent_id TEXT NOT NULL,
                        status TEXT NOT NULL,mode TEXT NOT NULL,result TEXT,PRIMARY KEY(run_id,step));
                    CREATE TABLE IF NOT EXISTS approval_requests(request_id TEXT PRIMARY KEY,run_id TEXT UNIQUE NOT NULL,
                        head_sha TEXT NOT NULL,status TEXT NOT NULL,result TEXT);
                    CREATE TABLE IF NOT EXISTS fault_resume_requests(request_id TEXT PRIMARY KEY,run_id TEXT UNIQUE NOT NULL,accepted_at REAL NOT NULL);
                    CREATE TABLE IF NOT EXISTS classification_followup_requests(request_id TEXT PRIMARY KEY,run_id TEXT UNIQUE NOT NULL,accepted_at REAL NOT NULL);
                    CREATE TABLE IF NOT EXISTS triage_continuation_requests(request_id TEXT PRIMARY KEY,run_id TEXT UNIQUE NOT NULL,original_task_id TEXT NOT NULL,accepted_at REAL NOT NULL);
                    CREATE TABLE IF NOT EXISTS calls(id INTEGER PRIMARY KEY,run_id TEXT NOT NULL,step TEXT NOT NULL,
                        intent_id TEXT NOT NULL,mode TEXT NOT NULL,status TEXT NOT NULL,started_at REAL NOT NULL,finished_at REAL);
                    CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,run_id TEXT NOT NULL,time TEXT NOT NULL,
                        stage TEXT NOT NULL,state TEXT NOT NULL,message TEXT NOT NULL,trace_id TEXT);
                """)
                identity = hashlib.sha256(encoded(self.scope).encode()).hexdigest()
                previous = db.execute("SELECT value FROM metadata WHERE key='scope'").fetchone()
                if previous and previous[0] != identity:
                    raise FlowError("Catalogue is bound to another immutable scope")
                db.execute("INSERT OR IGNORE INTO metadata VALUES('scope',?)", (identity,))
            self._recover()
        except BaseException:
            os.close(self._lease)
            self._lease = None
            raise
        if self.autostart:
            self._ensure_worker()

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def _transaction(self):
        with self._mutex, self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                db.execute("ROLLBACK")
                raise
            else:
                db.execute("COMMIT")

    def _event(self, db, run_id, value):
        if (not isinstance(value, dict) or set(value) - {"stage", "state", "message", "traceId"}
                or not all(isinstance(value.get(k), str) for k in ("stage", "state", "message"))
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value["stage"])
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", value["state"])
                or not 1 <= len(value["message"]) <= 240 or any(ord(c) < 32 for c in value["message"])
                or (value.get("traceId") is not None and not re.fullmatch(r"[0-9a-f]{32}", value["traceId"]))):
            raise FlowError("Invalid observed event")
        previous = db.execute('SELECT stage,state,message,trace_id FROM events WHERE run_id=? ORDER BY rowid DESC LIMIT 1', (run_id,)).fetchone()
        if previous and tuple(previous) == (value['stage'], value['state'], value['message'], value.get('traceId')):
            return
        db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?)", (uuid.uuid4().hex, run_id,
                   datetime.now(timezone.utc).isoformat(), value["stage"], value["state"], value["message"], value.get("traceId")))

    def _recover(self):
        with self._transaction() as db:
            row = db.execute("SELECT * FROM runs WHERE active=1 AND status='inflight'").fetchone()
            if not row:
                return
            intent = db.execute("SELECT * FROM intents WHERE run_id=? AND step=?", (row["run_id"], row["step"])).fetchone()
            safe = intent and (intent["mode"] == "observe" or row["step"] in READ_ONLY_STEPS)
            db.execute("UPDATE calls SET status='interrupted',finished_at=? WHERE run_id=? AND status='inflight'", (time.time(), row["run_id"]))
            db.execute("UPDATE intents SET status=? WHERE run_id=? AND step=?", ("pending" if safe else "unknown", row["run_id"], row["step"]))
            db.execute("UPDATE runs SET status=?,phase=?,next_poll=0,updated_at=? WHERE run_id=?",
                       ("pending" if safe else "stopped", row["phase"] if safe else "unknown", time.time(), row["run_id"]))
            self._event(db, row["run_id"], {"stage": row["step"], "state": "pending" if safe else "unknown",
                        "message": "Resuming observation of the recorded operation." if safe else "An external action was interrupted. Reconcile its original identity; no action was resent."})

    def start(self, request_id):
        try:
            request_id = str(uuid.UUID(request_id))
        except (ValueError, TypeError, AttributeError):
            raise FlowError("requestId must be a UUID") from None
        with self._transaction() as db:
            existing = db.execute("SELECT run_id FROM requests WHERE request_id=?", (request_id,)).fetchone()
            active = db.execute("SELECT run_id FROM runs WHERE active=1").fetchone()
            if existing or active:
                run_id = (existing or active)["run_id"]
            else:
                run_id = "demo-" + uuid.uuid4().hex
                config = self.config_factory(run_id) if self.config_factory else {**self.scope, "run_id": run_id}
                if not isinstance(config, dict) or len(encoded(config).encode()) > 65536:
                    raise FlowError("Invalid immutable run configuration")
                for key in ("run_id", "runId"):
                    if key in config and config[key] != run_id:
                        raise FlowError("Run configuration identity mismatch")
                directory = self.run_root / run_id
                directory.mkdir(parents=True, mode=0o700)
                fd = os.open(directory / "config.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as stream:
                    stream.write(encoded(config) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                now = time.time()
                db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,0)",
                           (run_id, STEPS[0], STEP_PHASE[STEPS[0]], "runnable", 1, encoded(config), "{}", now, now))
                self._event(db, run_id, {"stage": "prepare", "state": "accepted", "message": "Demo request accepted for the configured isolated scope."})
            db.execute("INSERT OR IGNORE INTO requests VALUES(?,?)", (request_id, run_id))
        if self.autostart:
            self._ensure_worker()
            self._wake.set()
        return self.public_state(run_id)

    @staticmethod
    def _resume_identity(request_id, run_id):
        try:
            if str(uuid.UUID(request_id)) != request_id:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise FlowError("requestId must be a canonical UUID") from None
        if not isinstance(run_id, str) or not re.fullmatch(r"demo-[a-f0-9]{32}", run_id):
            raise FlowError("An exact demo runId is required")

    def resume_readback(self, request_id, run_id):
        self._resume_identity(request_id, run_id)
        with self._connection() as db:
            request = db.execute('SELECT run_id FROM fault_resume_requests WHERE request_id=?', (request_id,)).fetchone()
            if request and request['run_id'] != run_id:
                raise ResumeConflict('Resume request belongs to another incident')
            existing = request or db.execute('SELECT run_id FROM fault_resume_requests WHERE run_id=?', (run_id,)).fetchone()
        return self.public_state(run_id) if existing else None

    @staticmethod
    def _fault_resume_eligible(db, row):
        if (not row or not row['active'] or row['status'] != 'stopped'
                or row['phase'] != 'blocked' or row['step'] != 'observe_fault'):
            return False
        data = json.loads(row['data'])
        if not re.fullmatch(r'[a-f0-9]{40}', str(data.get('adapter', {}).get('rollout_sha', ''))):
            return False
        if any(data.get(key, {}).get(field) is not None for key, field in (
                ('classifier', 'decision'), ('classifier', 'attempts'), ('native', 'taskId'),
                ('remedy', 'headSha'), ('approval', 'approvalId'), ('merge', 'taskId'), ('verification', 'taskId'))):
            return False
        intents = {item['step']: item['status'] for item in db.execute(
            'SELECT step,status FROM intents WHERE run_id=?', (row['run_id'],))}
        return (intents.get('prepare') == 'completed' and intents.get('inject_fault') == 'completed'
                and intents.get('observe_fault') == 'blocked'
                and not set(intents) - {'prepare', 'inject_fault', 'observe_fault'}
                and not db.execute('SELECT 1 FROM calls WHERE run_id=? AND step NOT IN (?,?,?)',
                    (row['run_id'], 'prepare', 'inject_fault', 'observe_fault')).fetchone())

    def resume_fault(self, request_id, run_id):
        """Reserve one fresh read-only fault window without replacing its predecessor."""
        prior = self.resume_readback(request_id, run_id)
        if prior is not None:
            return prior
        with self._connection() as db:
            row = db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
            eligible = self._fault_resume_eligible(db, row)
        if not eligible:
            prior = self.resume_readback(request_id, run_id)
            if prior is not None:
                return prior
            raise ResumeConflict('This incident cannot start a fresh fault observation')
        read = getattr(self.adapter, 'budget_state', None)
        try:
            budget = read(force=True) if callable(read) else None
        except Exception:
            budget = None
        if (not isinstance(budget, dict) or budget.get('available') is not True
                or budget.get('enabled') is not True
                or any(type(budget.get(k)) is not int or budget[k] <= 0
                       for k in ('requestsRemaining', 'inputBytesRemaining'))):
            prior = self.resume_readback(request_id, run_id)
            if prior is not None:
                return prior
            raise ResumeConflict('Resume needs a separately authorized available model allowance; no operation was repeated')
        if budget.get('boundRunId') is not None and budget['boundRunId'] != run_id:
            raise ResumeConflict('This allowance is reserved for another incident; no operation was repeated')
        with self._advance_mutex, self._transaction() as db:
            existing = db.execute('SELECT run_id FROM fault_resume_requests WHERE request_id=? OR run_id=?',
                                  (request_id, run_id)).fetchone()
            if existing:
                if existing['run_id'] != run_id:
                    raise ResumeConflict('Resume request belongs to another incident')
            else:
                row = db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
                if not self._fault_resume_eligible(db, row):
                    raise ResumeConflict('Incident state changed before resume was recorded')
                now = time.time()
                db.execute('INSERT INTO fault_resume_requests VALUES(?,?,?)', (request_id, run_id, now))
                db.execute("UPDATE runs SET step='recheck_fault',phase='observing',status='runnable',next_poll=0,updated_at=? WHERE run_id=?", (now, run_id))
                self._event(db, run_id, {'stage':'recheck_fault', 'state':'accepted',
                    'message':'Resume accepted for this incident: measure a fresh denial window. No fault, issue or agent action was resent.'})
        if self.autostart:
            self._ensure_worker()
        self._wake.set()
        return self.public_state(run_id)

    def _classification_followup_readback(self, request_id, run_id):
        self._resume_identity(request_id, run_id)
        with self._connection() as db:
            request = db.execute('SELECT run_id FROM classification_followup_requests WHERE request_id=?', (request_id,)).fetchone()
            if request and request['run_id'] != run_id:
                raise ResumeConflict('Followup request belongs to another incident')
            existing = request or db.execute('SELECT run_id FROM classification_followup_requests WHERE run_id=?', (run_id,)).fetchone()
        return self.public_state(run_id) if existing else None

    @staticmethod
    def _classification_followup_eligible(db, row):
        if (not row or not row['active'] or row['status'] != 'stopped'
                or row['phase'] != 'suppressed' or row['step'] != 'classify'):
            return False
        data = json.loads(row['data'])
        decision = data.get('classifier', {})
        confidence = decision.get('confidence')
        if (decision.get('decision') != 'investigate' or decision.get('severity') != 'critical'
                or type(confidence) not in {float, int} or not 0 <= confidence < 0.95
                or decision.get('threshold') != 0.95 or decision.get('attempts') != 1
                or not re.fullmatch(r'[a-f0-9]{40}', str(data.get('adapter', {}).get('rollout_sha', '')))
                or not re.fullmatch(r'[a-f0-9]{64}', str(data.get('adapter', {}).get('candidate_id', '')))):
            return False
        if any(data.get(key, {}).get(field) is not None for key, field in (
                ('native', 'taskId'), ('remedy', 'headSha'), ('approval', 'approvalId'),
                ('merge', 'taskId'), ('verification', 'taskId'))):
            return False
        intents = {item['step']: item['status'] for item in db.execute(
            'SELECT step,status FROM intents WHERE run_id=?', (row['run_id'],))}
        return (intents.get('prepare') == 'completed' and intents.get('inject_fault') == 'completed'
                and intents.get('classify') == 'suppressed'
                and (intents.get('observe_fault') == 'completed' or intents.get('recheck_fault') == 'completed')
                and not set(intents) - {'prepare', 'inject_fault', 'observe_fault', 'recheck_fault', 'classify'}
                and not db.execute('SELECT 1 FROM calls WHERE run_id=? AND step NOT IN (?,?,?,?,?)',
                    (row['run_id'], 'prepare', 'inject_fault', 'observe_fault', 'recheck_fault', 'classify')).fetchone())

    def request_classification_followup(self, request_id, run_id):
        """Reserve one operator-requested fresh window and classification, never resend a candidate."""
        prior = self._classification_followup_readback(request_id, run_id)
        if prior is not None:
            return prior
        with self._connection() as db:
            row = db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
            eligible = self._classification_followup_eligible(db, row)
        if not eligible:
            prior = self._classification_followup_readback(request_id, run_id)
            if prior is not None:
                return prior
            raise ResumeConflict('Only a first critical confidence suppression permits this one fresh followup')
        read = getattr(self.adapter, 'budget_state', None)
        try:
            budget = read(force=True) if callable(read) else None
        except Exception:
            budget = None
        if (not isinstance(budget, dict) or budget.get('available') is not True
                or budget.get('enabled') is not True
                or any(type(budget.get(k)) is not int or budget[k] <= 0
                       for k in ('requestsRemaining', 'inputBytesRemaining'))
                or budget.get('boundRunId') not in {None, run_id}):
            prior = self._classification_followup_readback(request_id, run_id)
            if prior is not None:
                return prior
            raise ResumeConflict('Followup requires an available allowance for this incident')
        with self._advance_mutex, self._transaction() as db:
            existing = db.execute('SELECT run_id FROM classification_followup_requests WHERE request_id=? OR run_id=?',
                                  (request_id, run_id)).fetchone()
            if existing:
                if existing['run_id'] != run_id:
                    raise ResumeConflict('Followup request belongs to another incident')
            else:
                row = db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
                if not self._classification_followup_eligible(db, row):
                    raise ResumeConflict('Incident changed before fresh followup was recorded')
                now = time.time()
                db.execute('INSERT INTO classification_followup_requests VALUES(?,?,?)', (request_id, run_id, now))
                db.execute("UPDATE runs SET step='classification_followup',phase='classifying',status='runnable',next_poll=0,updated_at=? WHERE run_id=?", (now, run_id))
                self._event(db, run_id, {'stage':'classification_followup', 'state':'accepted',
                    'message':'Operator requested one fresh observation window and classification. The original suppression and 0.95 gate remain unchanged.'})
        if self.autostart:
            self._ensure_worker()
        self._wake.set()
        return self.public_state(run_id)

    def _triage_continuation_readback(self, request_id, run_id):
        self._resume_identity(request_id, run_id)
        with self._connection() as db:
            request = db.execute('SELECT run_id FROM triage_continuation_requests WHERE request_id=?', (request_id,)).fetchone()
            if request and request['run_id'] != run_id:
                raise ResumeConflict('Continuation request belongs to another incident')
            existing = request or db.execute('SELECT run_id FROM triage_continuation_requests WHERE run_id=?', (run_id,)).fetchone()
        return self.public_state(run_id) if existing else None

    @staticmethod
    def _triage_continuation_eligible(db, row):
        if (not row or not row['active'] or row['status'] != 'stopped'
                or row['phase'] != 'blocked' or row['step'] != 'triage'):
            return False
        data = json.loads(row['data'])
        native, adapter, decision = data.get('native', {}), data.get('adapter', {}), data.get('classifier', {})
        if (not isinstance(native.get('taskId'), str) or not native['taskId']
                or native['taskId'] != adapter.get('task_id') or not isinstance(adapter.get('session_id'), str)
                or not adapter['session_id'] or decision.get('decision') != 'investigate'
                or decision.get('severity') != 'critical' or type(decision.get('confidence')) not in {int, float}
                or not .95 <= decision['confidence'] <= 1):
            return False
        if any(data.get(key, {}).get(field) is not None for key, field in (
                ('remedy', 'headSha'), ('approval', 'approvalId'), ('merge', 'taskId'), ('verification', 'taskId'))):
            return False
        intents = {item['step']: item['status'] for item in db.execute(
            'SELECT step,status FROM intents WHERE run_id=?', (row['run_id'],))}
        return (intents.get('dispatch') == 'completed' and intents.get('triage') == 'blocked'
                and not set(intents) - {'prepare', 'inject_fault', 'observe_fault', 'recheck_fault',
                                       'classify', 'classification_followup', 'dispatch', 'triage'})

    def request_triage_continuation(self, request_id, run_id):
        """Reserve one explicitly requested native continuation after credential repair."""
        prior = self._triage_continuation_readback(request_id, run_id)
        if prior is not None:
            return prior
        with self._connection() as db:
            row = db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
            eligible = self._triage_continuation_eligible(db, row)
            run = self._run(row) if eligible else None
        if not eligible:
            prior = self._triage_continuation_readback(request_id, run_id)
            if prior is not None:
                return prior
            raise ResumeConflict('Only a stopped pre-proposal triage permits this continuation')
        try:
            budget = self.adapter.budget_state(force=True)
            if (not isinstance(budget, dict) or budget.get('available') is not True
                    or budget.get('enabled') is not True
                    or any(type(budget.get(k)) is not int or budget[k] <= 0
                           for k in ('requestsRemaining', 'inputBytesRemaining'))
                    or budget.get('boundRunId') not in {None, run_id}):
                raise ValueError()
            checked = self.adapter.validate_triage_continuation(run)
            if (checked.get('taskId') != run['data']['native']['taskId']
                    or checked.get('sessionId') != run['data']['adapter']['session_id']):
                raise ValueError()
        except Exception:
            prior = self._triage_continuation_readback(request_id, run_id)
            if prior is not None:
                return prior
            raise ResumeConflict('Continuation requires a completed original task, restored repository access and an available incident allowance') from None
        with self._advance_mutex, self._transaction() as db:
            existing = db.execute('SELECT run_id FROM triage_continuation_requests WHERE request_id=? OR run_id=?',
                                  (request_id, run_id)).fetchone()
            if existing:
                if existing['run_id'] != run_id:
                    raise ResumeConflict('Continuation request belongs to another incident')
            else:
                row = db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
                if not self._triage_continuation_eligible(db, row):
                    raise ResumeConflict('Incident changed before continuation was recorded')
                now = time.time()
                db.execute('INSERT INTO triage_continuation_requests VALUES(?,?,?,?)', (request_id, run_id, checked['taskId'], now))
                db.execute("UPDATE runs SET step='triage_continuation',phase='triaging',status='runnable',next_poll=0,updated_at=? WHERE run_id=?", (now, run_id))
                self._event(db, run_id, {'stage':'triage_continuation', 'state':'accepted',
                    'message':'Operator requested one native continuation after credential repair. The original task and failure remain recorded.'})
        if self.autostart:
            self._ensure_worker()
        self._wake.set()
        return self.public_state(run_id)

    def approve(self, request_id, run_id, head_sha):
        try:
            if str(uuid.UUID(request_id)) != request_id:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise FlowError("requestId must be a canonical UUID") from None
        if (not isinstance(run_id, str) or not isinstance(head_sha, str)
                or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", head_sha)):
            raise FlowError("An exact runId and headSha are required")
        with self._advance_mutex:
            with self._transaction() as db:
                reused = db.execute('SELECT * FROM approval_requests WHERE request_id=?', (request_id,)).fetchone()
                if reused and (reused['run_id'] != run_id or reused['head_sha'] != head_sha):
                    raise ApprovalConflict('Approval request identity was already used for another binding')
                row = db.execute('SELECT * FROM runs WHERE run_id=?', (run_id,)).fetchone()
                if not row:
                    raise ApprovalConflict('The requested incident is not present')
                existing = db.execute('SELECT * FROM approval_requests WHERE run_id=?', (run_id,)).fetchone()
                if existing and existing['head_sha'] != head_sha:
                    raise ApprovalConflict('The requested head differs from the recorded approval')
                if existing and existing['status'] == 'recorded':
                    return self.public_state(run_id)
                data = json.loads(row['data'])
                remedy = data.get('remedy', {})
                if (not row['active'] or row['step'] != 'await_approval' or row['phase'] != 'waiting_human'
                        or row['status'] not in {'runnable', 'pending'}
                        or remedy.get('headSha') != head_sha or remedy.get('ci') != 'passed'
                        or remedy.get('review') != 'passed'):
                    raise ApprovalConflict('Approval requires the current reviewed head at the dashboard human gate')
                if existing and existing['status'] == 'rejected':
                    raise ApprovalConflict('The recorded approval was rejected and requires incident review')
                canonical_id = existing['request_id'] if existing else request_id
                mode = 'observe' if existing else 'execute'
                if not existing:
                    db.execute("INSERT INTO approval_requests VALUES(?,?,?,'pending',NULL)", (canonical_id, run_id, head_sha))
                    self._event(db, run_id, {'stage':'await_approval', 'state':'requested',
                                'message':'Human dashboard approval requested for the displayed exact commit.'})
                run = self._run(row)
                run['_call'] = {'intentId':canonical_id, 'mode':mode}
            try:
                receipt = self.adapter.approve(run, canonical_id, head_sha, observe=mode == 'observe')
                if isinstance(receipt, dict):
                    receipt = {field:receipt.get(field) for field in PUBLIC_FIELDS['approval']}
                self._validate_approval(receipt, canonical_id, head_sha)
            except Exception as error:
                rejected = isinstance(error, ApprovalConflict)
                with self._transaction() as db:
                    db.execute('UPDATE approval_requests SET status=? WHERE run_id=?', ('rejected' if rejected else 'unknown', run_id))
                    self._event(db, run_id, {'stage':'await_approval', 'state':'rejected' if rejected else 'unknown',
                        'message':'The exact-head approval was rejected. Incident review is required.' if rejected else
                                  'Approval outcome is unknown. Read back the original grant; no second approval was sent.'})
                if rejected:
                    raise ApprovalConflict('The current repository checks no longer match this approval') from None
                raise ApprovalUnknown('Approval outcome requires original-grant readback') from None
            with self._transaction() as db:
                latest = db.execute('SELECT data FROM runs WHERE run_id=?', (run_id,)).fetchone()
                updated = merged(json.loads(latest['data']), {'approval':receipt})
                db.execute("UPDATE approval_requests SET status='recorded',result=? WHERE run_id=?", (encoded(receipt), run_id))
                db.execute('UPDATE runs SET data=?,next_poll=0,updated_at=? WHERE run_id=?', (encoded(updated), time.time(), run_id))
                self._event(db, run_id, {'stage':'await_approval', 'state':'approved',
                    'message':'Human approval recorded for the exact reviewed commit. Kagent may now perform the guarded merge.'})
        self._wake.set()
        return self.public_state(run_id)

    @staticmethod
    def _validate_approval(receipt, request_id, head_sha):
        if (not isinstance(receipt, dict) or receipt.get('approvalId') != request_id
                or receipt.get('headSha') != head_sha or receipt.get('state') != 'approved'
                or type(receipt.get('approvedBy')) is not int or receipt['approvedBy'] < 1
                or type(receipt.get('approvedAt')) is not int or type(receipt.get('expiresAt')) is not int
                or not receipt['approvedAt'] <= time.time() < receipt['expiresAt']
                or not 0 < receipt['expiresAt'] - receipt['approvedAt'] <= 900):
            raise ApprovalUnknown('A current actual exact-head approval receipt is required')

    def _run(self, row):
        return {"runId": row["run_id"], "step": row["step"], "phase": row["phase"], "status": row["status"],
                "config": json.loads(row["config"]), "configPath": str(self.run_root / row["run_id"] / "config.json"),
                "workspace": str((self.run_root / row["run_id"]).resolve()),
                "data": json.loads(row["data"])}

    def _proof(self, run, closed=False):
        if not callable(self.closure_verifier):
            return False
        value = self.closure_verifier(run)
        proof = ClosureProof(**value) if isinstance(value, dict) else value
        task = run["data"].get("verification", {}).get("taskId")
        valid = (isinstance(proof, ClosureProof) and proof.verified is True and isinstance(task, str) and bool(task)
                 and proof.task_id == task and proof.task_state in TERMINAL_NATIVE
                 and isinstance(proof.evidence_digest, str) and re.fullmatch(r"[0-9a-f]{64}", proof.evidence_digest))
        if not valid or not closed:
            return bool(valid)
        ticket = run["data"].get("ticket", {})
        return (proof.issue_closed is True and type(proof.issue_iid) is int and proof.issue_iid > 0
                and proof.issue_iid == ticket.get("iid") and ticket.get("state") == "closed")

    def _check_completed(self, run, step):
        data = run["data"]
        if step == "recheck_fault" and not re.fullmatch(r'[a-f0-9]{64}', str(data.get('adapter', {}).get('candidate_id', ''))):
            raise FlowError('A candidate bound to the fresh recheck window is required')
        if step in {"classify", "classification_followup"}:
            decision = data.get("classifier", {})
            confidence = decision.get("confidence")
            if (decision.get("decision") != "investigate" or decision.get("severity") != "critical"
                    or type(confidence) not in {int, float} or not 0.95 <= confidence <= 1
                    or decision.get("threshold", 0.95) != 0.95):
                raise FlowError("An actual admitted critical classifier decision is required")
        if step == "classification_followup" and not re.fullmatch(r'[a-f0-9]{64}', str(data.get('adapter', {}).get('candidate_id', ''))):
            raise FlowError('The followup requires its own actual fresh candidate')
        if step == 'triage_continuation':
            native, remedy = data.get('native', {}), data.get('remedy', {})
            with self._connection() as db:
                request = db.execute('SELECT original_task_id FROM triage_continuation_requests WHERE run_id=?', (run['runId'],)).fetchone()
            if (not request or not native.get('taskId') or native['taskId'] == request['original_task_id']
                    or native.get('state') not in TERMINAL_NATIVE or data.get('adapter', {}).get('task_id') != native['taskId']
                    or not re.fullmatch(r'[a-f0-9]{40}', str(remedy.get('headSha', ''))) or remedy.get('ci') != 'passed'):
                raise FlowError('A distinct completed continuation task and exact-head passing CI are required')
        if step == "await_approval":
            approval = data.get('approval', {})
            with self._connection() as db:
                request = db.execute('SELECT * FROM approval_requests WHERE run_id=?', (run['runId'],)).fetchone()
            if not request or request['status'] == 'rejected' or request['head_sha'] != data.get('remedy', {}).get('headSha'):
                raise FlowError('The actual matching dashboard approval request is required')
            self._validate_approval(approval, request['request_id'], data.get('remedy', {}).get('headSha'))
        if step == "merge":
            merge = data.get('merge', {})
            if (not isinstance(merge.get('taskId'), str) or not merge['taskId']
                    or merge.get('taskState') not in TERMINAL_NATIVE
                    or not data.get('approval', {}).get('approvalId')
                    or merge.get('approvalId') != data['approval']['approvalId']):
                raise FlowError('A completed native merge task bound to the human approval is required')
        if step == "observe_merge":
            merge = data.get("merge", {})
            if (merge.get("status") != "merged" or not isinstance(merge.get("sha"), str)
                    or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", merge["sha"]) or not merge.get("mergedBy")
                    or not data.get("approval", {}).get("approvalId")
                    or merge.get("approvalId") != data["approval"]["approvalId"]):
                raise FlowError("An exact observed approved-agent merge receipt is required")

    def run_once(self):
        """Advance once, useful for tests and a foreground operator loop."""
        if not self._advance_mutex.acquire(blocking=False):
            return self.public_state()
        run = None
        try:
            with self._transaction() as db:
                row = db.execute("SELECT * FROM runs WHERE active=1 AND status IN ('runnable','pending')").fetchone()
                if not row or row["next_poll"] > time.time():
                    return self.public_state()
                run, step = self._run(row), row["step"]
                previous = db.execute("SELECT * FROM intents WHERE run_id=? AND step=?", (row["run_id"], step)).fetchone()
            budget_hook = getattr(self.adapter, 'execution_budget', None)
            if step in {'merge', 'verify'} and previous is None and callable(budget_hook):
                try:
                    budget = budget_hook(step)
                    ready = (isinstance(budget, dict) and budget.get('ready') is True
                             and budget.get('boundRunId') in {None, run['runId']})
                except Exception:
                    ready = False
                if not ready:
                    with self._transaction() as db:
                        current = db.execute("SELECT * FROM runs WHERE run_id=? AND active=1", (run['runId'],)).fetchone()
                        reserved = db.execute("SELECT 1 FROM intents WHERE run_id=? AND step=?", (run['runId'], step)).fetchone()
                        if (current and current['step'] == step and current['status'] in {'runnable', 'pending'}
                                and not reserved):
                            now = time.time()
                            db.execute("UPDATE runs SET status='pending',phase=?,next_poll=?,updated_at=? WHERE run_id=?",
                                       (STEP_PHASE[step], now + 5, now, run['runId']))
                            self._event(db, run['runId'], {'stage':step, 'state':'pending',
                                'message':'Waiting for model allowance to complete merge and verification; no native task was sent.'})
                    return self.public_state(run['runId'])
            with self._transaction() as db:
                row = db.execute("SELECT * FROM runs WHERE run_id=? AND active=1", (run['runId'],)).fetchone()
                if (not row or row['step'] != step or row['status'] not in {'runnable', 'pending'}
                        or row['next_poll'] > time.time()):
                    return self.public_state(run['runId'])
                run = self._run(row)
                previous = db.execute("SELECT * FROM intents WHERE run_id=? AND step=?", (run['runId'], step)).fetchone()
                intent_id, mode = (previous["intent_id"], "observe") if previous else (uuid.uuid4().hex, "execute")
                db.execute("INSERT INTO intents VALUES(?,?,?,?,?,NULL) ON CONFLICT(run_id,step) DO UPDATE SET status='inflight',mode=excluded.mode",
                           (row["run_id"], step, intent_id, "inflight", mode))
                call_id = db.execute("INSERT INTO calls(run_id,step,intent_id,mode,status,started_at) VALUES(?,?,?,?,'inflight',?)",
                                     (row["run_id"], step, intent_id, mode, time.time())).lastrowid
                db.execute("UPDATE runs SET status='inflight',updated_at=? WHERE run_id=?", (time.time(), row["run_id"]))
            run["_call"] = {"intentId": intent_id, "mode": mode}
            if self.telemetry is not None:
                try:
                    carrier = self.telemetry.begin(run, step)
                    if carrier:
                        run["_traceparent"] = carrier
                except Exception:
                    pass
            if step == "close" and not self._proof(run):
                result = StepResult("blocked", events=({"stage": step, "state": "blocked", "message": "Issue closure requires complete evidence and an actual completed native verification task."},))
            else:
                result = StepResult.parse(self.adapter.advance(run, step))
            proposed = {**run, "data": merged(run["data"], result.patch)}
            proposed["data"].setdefault("ticket", {})["closedVerified"] = False
            if len(encoded(proposed["data"]).encode()) > 262144:
                raise FlowError("Run data exceeds its retained limit")
            if result.status == "completed":
                self._check_completed(proposed, step)
                if step == "close" and not self._proof(proposed, closed=True):
                    raise FlowError("The actual closed issue readback is not proven")
            phase = result.phase or STEP_PHASE[step]
            if result.status == "pending" and phase not in PENDING_PHASES[step]:
                raise FlowError("Adapter phase cannot skip a flow step")
            status, next_step, active, delay = "stopped", step, 1, 0
            if result.status == "completed":
                if step == "close":
                    phase, status, active = "closed", "complete", 0
                    proposed["data"]["ticket"]["closedVerified"] = True
                else:
                    next_step = NEXT_STEP[step]
                    phase = "fault_injected" if step == "inject_fault" else STEP_PHASE[next_step]
                    status = "runnable"
            elif result.status == "pending":
                status, delay = "pending", result.poll_after
            else:
                phase = result.status
            with self._transaction() as db:
                if step == 'await_approval' and result.status == 'completed':
                    db.execute("UPDATE approval_requests SET status='recorded',result=? WHERE run_id=?",
                               (encoded(proposed['data']['approval']), run['runId']))
                for event in result.events:
                    self._event(db, run["runId"], event)
                db.execute("UPDATE intents SET status=?,result=? WHERE run_id=? AND step=?",
                           (result.status, encoded(asdict(result)), run["runId"], step))
                db.execute("UPDATE calls SET status=?,finished_at=? WHERE id=?", (result.status, time.time(), call_id))
                db.execute("UPDATE runs SET step=?,phase=?,status=?,active=?,data=?,updated_at=?,next_poll=? WHERE run_id=?",
                           (next_step, phase, status, active, encoded(proposed["data"]), time.time(), time.time() + delay, run["runId"]))
            if self.telemetry is not None:
                try:
                    self.telemetry.observe(run, step, result)
                except Exception:
                    pass
        except Exception as error:
            if run is not None:
                if self.telemetry is not None:
                    try:
                        self.telemetry.observe(run, run["step"], error=error)
                    except Exception:
                        pass
                with self._transaction() as db:
                    db.execute("UPDATE runs SET phase='unknown',status='stopped',updated_at=? WHERE run_id=?", (time.time(), run["runId"]))
                    db.execute("UPDATE intents SET status='unknown' WHERE run_id=? AND step=?", (run["runId"], run["step"]))
                    db.execute("UPDATE calls SET status='unknown',finished_at=? WHERE run_id=? AND status='inflight'", (time.time(), run["runId"]))
                    self._event(db, run["runId"], {"stage": run["step"], "state": "unknown", "message": "The operation needs read-only reconciliation. No retry was made. Failure type " + type(error).__name__[:60] + "."})
            else:
                raise
        finally:
            self._advance_mutex.release()
        return self.public_state(run["runId"] if run else None)

    def public_state(self, run_id=None):
        with self._mutex, self._connection() as db:
            row = db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone() if run_id else db.execute("SELECT * FROM runs ORDER BY active DESC,created_at DESC LIMIT 1").fetchone()
            data = json.loads(row["data"]) if row else {}
            result = {"enabled": True, "runId": row["run_id"] if row else None, "phase": row["phase"] if row else "ready",
                      "running": bool(row and row["status"] in {"runnable", "pending", "inflight"})}
            for key, defaults in PUBLIC_FIELDS.items():
                supplied = data.get(key, {})
                result[key] = {field: supplied.get(field, default) for field, default in defaults.items()} if isinstance(supplied, dict) else dict(defaults)
            result["ticket"]["closedVerified"] = bool(row and row["phase"] == "closed" and result["ticket"]["closedVerified"] is True)
            events = db.execute("""WITH observations AS (
                SELECT rowid AS sequence,*,LAG(stage) OVER (ORDER BY rowid) AS prior_stage,
                LAG(state) OVER (ORDER BY rowid) AS prior_state,LAG(message) OVER (ORDER BY rowid) AS prior_message,
                LAG(trace_id) OVER (ORDER BY rowid) AS prior_trace FROM events WHERE run_id=?)
                SELECT * FROM observations WHERE NOT (stage IS prior_stage AND state IS prior_state
                AND message IS prior_message AND trace_id IS prior_trace) ORDER BY sequence DESC LIMIT 100""", (row["run_id"],)).fetchall() if row else []
            result["events"] = [{"id": event["id"], "time": event["time"], "stage": event["stage"], "state": event["state"],
                                 "message": event["message"], **({"traceId": event["trace_id"]} if event["trace_id"] else {})} for event in reversed(events)]
            active = db.execute("SELECT run_id FROM runs WHERE active=1").fetchone()
            approval_request = db.execute('SELECT * FROM approval_requests WHERE run_id=?', (row['run_id'],)).fetchone() if row else None
            resume_eligible = self._fault_resume_eligible(db, row)
        if approval_request and result['approval']['state'] != 'approved':
            result['approval'].update(approvalId=approval_request['request_id'], headSha=approval_request['head_sha'], state=approval_request['status'])
        url = result["remedy"]["mrUrl"]
        stopped = bool(row and row['active'] and row['status'] == 'stopped')
        start_reason = ('This incident stopped during fault observation. Resume this incident when its model allowance is available.'
                        if resume_eligible else 'This incident is stopped and needs reconciliation; waiting will not finish it.'
                        if stopped else 'The current incident must finish before another demo can start.')
        result["actions"] = {"start": {"enabled": active is None, "reason": None if active is None else start_reason},
                             "resume": {"enabled": resume_eligible, "reason": None if resume_eligible else 'Fresh fault observation is available only for a stopped pre-classifier admission window.'},
                             "review": {"enabled": bool(url), "url": url}}
        approval_ready = bool(row and row['active'] and row['step'] == 'await_approval'
                              and row['phase'] == 'waiting_human' and row['status'] in {'runnable', 'pending', 'inflight'}
                              and result['remedy']['ci'] == 'passed' and result['remedy']['review'] == 'passed'
                              and result['remedy']['headSha'] and approval_request is None)
        reason = None if approval_ready else ('Approval is already recorded or requires original-grant readback.' if approval_request else
                                              'Approval is available after the exact-head checks and independent review pass.')
        result['actions']['approve'] = {'enabled':approval_ready, 'reason':reason}
        return result

    def _ensure_worker(self):
        with self._mutex:
            if self._stop.is_set() or (self._thread and self._thread.is_alive()):
                return
            self._thread = threading.Thread(target=self._worker, name="kyverno-demo-controller", daemon=True)
            self._thread.start()

    def trace_context(self):
        """Actual dispatch session identity for joining received native telemetry."""
        with self._mutex, self._connection() as db:
            row = db.execute("SELECT data FROM runs ORDER BY active DESC,created_at DESC LIMIT 1").fetchone()
        return json.loads(row['data']).get('adapter', {}).get('session_id') if row else None

    def trace_contexts(self):
        with self._mutex, self._connection() as db:
            row = db.execute("SELECT data FROM runs ORDER BY active DESC,created_at DESC LIMIT 1").fetchone()
        adapter = json.loads(row['data']).get('adapter', {}) if row else {}
        return {field: adapter.get(key) for field, key in (
            ('native', 'session_id'), ('merge', 'merge_session_id'), ('verification', 'verification_session_id'))}

    def evidence_context(self):
        """Actual task and session anchors for the current run's received traces."""
        with self._mutex, self._connection() as db:
            row = db.execute("SELECT run_id,data FROM runs ORDER BY active DESC,created_at DESC LIMIT 1").fetchone()
            steps = [item['step'] for item in db.execute(
                'SELECT step FROM intents WHERE run_id=? LIMIT 32', (row['run_id'],))] if row else []
            continuation_request = db.execute('SELECT original_task_id FROM triage_continuation_requests WHERE run_id=?', (row['run_id'],)).fetchone() if row else None
        data = json.loads(row['data']) if row else {}
        adapter = data.get('adapter', {})
        tasks = {}
        for role, prefix, state in (
            ('triage', '', data.get('native', {}).get('state')),
            ('review', 'review_', adapter.get('review_state')),
            ('merge', 'merge_', data.get('merge', {}).get('taskState')),
            ('verify', 'verification_', data.get('verification', {}).get('state')),
        ):
            tasks[role] = {'taskId': adapter.get(prefix + 'task_id'),
                           'sessionId': adapter.get(prefix + 'session_id')}
            if state is not None:
                tasks[role]['state'] = state
        if continuation_request:
            try:
                workspace = self.run_root / row['run_id']
                records = {}
                for name in ('operator-triage-continuation', 'triage-continuation-send'):
                    fd = os.open(workspace / (name + '.json'), os.O_RDONLY | os.O_NOFOLLOW)
                    with os.fdopen(fd, 'rb') as stream:
                        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                            raise ValueError()
                        raw = stream.read(131073)
                    if len(raw) > 131072:
                        raise ValueError()
                    records[name] = (json.loads(raw), raw)
                receipt = records['operator-triage-continuation'][0]
                sent, raw_send = records['triage-continuation-send']
                accepted = sent.get('result', {}).get('task', {})
                if (sent.get('state') != 'completed' or receipt.get('original_task_id') != continuation_request['original_task_id']
                        or receipt.get('task_id') != data.get('native', {}).get('taskId')
                        or receipt.get('task_id') != accepted.get('id')
                        or receipt.get('session_id') != adapter.get('session_id')
                        or receipt.get('session_id') != accepted.get('contextId')
                        or receipt.get('send_receipt_sha256') != hashlib.sha256(raw_send).hexdigest()):
                    raise ValueError()
                tasks['triage_original'] = {'taskId':receipt['original_task_id'], 'sessionId':receipt['session_id'],
                                             'state':'TASK_STATE_COMPLETED'}
            except (OSError, ValueError, TypeError, KeyError):
                pass
        coordinator = []
        if row:
            workspace = self.run_root / row['run_id']
            for step in steps:
                if step not in STEP_PHASE or workspace.is_symlink():
                    continue
                path = workspace / ('.flow-telemetry-' + step + '.json')
                try:
                    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0))
                    with os.fdopen(fd, 'rb') as stream:
                        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                            continue
                        raw = stream.read(4097)
                    if len(raw) > 4096:
                        continue
                    value = json.loads(raw)
                    if (not isinstance(value, dict) or value.get('runId') != row['run_id']
                            or value.get('step') != step
                            or not re.fullmatch(r'[a-f0-9]{32}', str(value.get('traceId', '')))
                            or not int(value['traceId'], 16)
                            or not re.fullmatch(r'[a-f0-9]{16}', str(value.get('spanId', '')))
                            or not int(value['spanId'], 16)
                            or type(value.get('started_ns')) is not int or not 0 < value['started_ns'] < 2**64):
                        continue
                    coordinator.append({'runId':row['run_id'], 'step':step, 'traceId':value['traceId'],
                                        'spanId':value['spanId'], 'startedNs':str(value['started_ns'])})
                except (OSError, ValueError, TypeError):
                    continue
        return {'runId': row['run_id'] if row else None, 'tasks': tasks, 'coordinatorContexts':coordinator}

    def _worker(self):
        while not self._stop.is_set():
            self._wake.clear()
            self.run_once()
            with self._connection() as db:
                row = db.execute("SELECT status,next_poll FROM runs WHERE active=1").fetchone()
            delay = max(0.01, row["next_poll"] - time.time()) if row and row["status"] == "pending" else 0.01 if row and row["status"] == "runnable" else self.poll_interval
            self._wake.wait(min(60, delay))

    def close(self, timeout=5):
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout)
            if self._thread.is_alive():
                raise FlowError("Adapter is still running; controller lease remains held")
        if self._lease is not None:
            os.close(self._lease)
            self._lease = None
