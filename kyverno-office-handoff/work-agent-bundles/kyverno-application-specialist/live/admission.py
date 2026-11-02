"""Durable deterministic admission, real-classifier callback and one-task outbox.

Observation authenticity belongs to the bounded trusted probe collector. This
module validates consistency and scope; untrusted model output cannot expand it.
"""
from dataclasses import dataclass
import itertools
import json
import math
from pathlib import Path
import time

from core import (CAUSE, FAULTY_PATTERN, POLICY_OBSERVATION_METHOD, Config, Ledger, Phase, Rejected,
                  canonical, digest, exact, git_sha, hash_value, ident, integer, validate_policy_bracket)

MAX_CANDIDATE = 16384
MAX_CLASSIFICATIONS = 12
MAX_OUTPUT_TOKENS = 512
MAX_INPUT_TOKENS = 16384
VALID_IMAGE = "docker.io/library/busybox:1.36"


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    evidence_ids: tuple
    packet: dict


class Admission:
    def __init__(self, config, db_path_or_ledger, now=time.time):
        self.config = Config.from_dict(config) if isinstance(config, dict) else config
        self.ledger = db_path_or_ledger if isinstance(db_path_or_ledger, Ledger) else Ledger(Path(db_path_or_ledger), self.config.identity)
        self.now = now

    def _scope(self, packet):
        c = self.config
        return all(packet.get(k) == getattr(c, k) for k in
                   ("cluster_id", "namespace", "application", "policy_name", "rule_name"))

    def _validate_observation(self, p):
        exact(p, ("schema_version", "cluster_id", "namespace", "application", "policy_name", "rule_name", "cause", "probe", "policy", "denial", "rollout"))
        if p["schema_version"] != 1 or type(p["schema_version"]) is not int:
            raise Rejected("Unsupported observation version")
        if len(canonical(p)) > MAX_CANDIDATE:
            raise Rejected("Observation exceeds candidate limit")
        exact(p["probe"], ("probe_id", "observed_at", "kind", "result", "image"))
        probe = p["probe"]
        ident(probe["probe_id"])
        integer(probe["observed_at"], 1)
        if probe["kind"] not in {"valid", "invalid"} or probe["result"] not in {"admitted", "denied", "error"}:
            raise Rejected("Invalid probe observation")
        exact(p["policy"], ("uid", "generation", "observed_generation", "policy_spec_sha256", "policy_revision", "image_pattern"),
              ("observation_method", "policy_read_before", "policy_read_after"))
        ident(p["policy"]["uid"])
        integer(p["policy"]["generation"], 1)
        if p["policy"]["observed_generation"] is not None:
            integer(p["policy"]["observed_generation"], 1)
        hash_value(p["policy"]["policy_spec_sha256"])
        git_sha(p["policy"]["policy_revision"])
        exact(p["denial"], ("source", "policy_name", "rule_name"))
        exact(p["rollout"], ("uid", "generation", "observed_generation", "desired_replicas", "updated_replicas", "available_replicas", "failed_create", "event_id", "policy_name", "rule_name"))
        rollout = p["rollout"]
        ident(rollout["uid"])
        ident(rollout["event_id"])
        for key in ("generation", "observed_generation", "desired_replicas"):
            integer(rollout[key], 1)
        for key in ("updated_replicas", "available_replicas"):
            integer(rollout[key])
        if type(rollout["failed_create"]) is not bool:
            raise Rejected("Invalid rollout corroboration")

    def _policy_current(self, packet):
        p = packet["policy"]
        if p["observed_generation"] == p["generation"]:
            return True
        if p["observed_generation"] is not None or p.get("observation_method") != POLICY_OBSERVATION_METHOD:
            return False
        try:
            validate_policy_bracket(p.get("policy_read_before"), p.get("policy_read_after"), p["uid"], p["generation"],
                                    p["policy_spec_sha256"], [packet["probe"]["observed_at"]], self.now(), self.config.evidence_max_age_seconds)
        except Rejected:
            return False
        return True

    def observe(self, packet):
        self._validate_observation(packet)
        c, probe, policy, rollout = self.config, packet["probe"], packet["policy"], packet["rollout"]
        reason = None
        if not self._scope(packet) or packet["cause"] != CAUSE:
            reason = "outside_allowlisted_condition"
        elif probe["kind"] != "valid" or probe["result"] != "denied" or probe["image"] != VALID_IMAGE:
            reason = "normal_enforcement_or_non_denial"
        elif not self.now() - c.evidence_max_age_seconds <= probe["observed_at"] <= self.now():
            reason = "stale_or_future_observation"
        elif (policy["policy_spec_sha256"] != c.faulty_policy_spec_sha256 or policy["image_pattern"] != FAULTY_PATTERN
              or not self._policy_current(packet)):
            reason = "faulty_policy_not_current"
        elif packet["denial"] != {"source": "kubernetes-dry-run", "policy_name": c.policy_name, "rule_name": c.rule_name}:
            reason = "policy_specific_denial_missing"
        elif (not rollout["failed_create"] or rollout["generation"] != rollout["observed_generation"]
              or rollout["desired_replicas"] != 1 or rollout["updated_replicas"] != 0 or rollout["available_replicas"] != 0
              or rollout["policy_name"] != c.policy_name or rollout["rule_name"] != c.rule_name):
            reason = "blocked_rollout_missing"
        if reason:
            self.ledger.count("suppressed_" + reason)
            return {"state": "suppressed", "reason": reason}
        value_hash, probe_id = digest(packet), probe["probe_id"]
        with self.ledger.transaction() as db:
            previous = db.execute("SELECT payload_hash FROM observations WHERE id=?", (probe_id,)).fetchone()
            if previous:
                if previous["payload_hash"] != value_hash:
                    raise Rejected("Observation ID reused with different evidence")
                return {"state": "replay", "probe_id": probe_id}
            if db.execute("SELECT COUNT(*) FROM observations").fetchone()[0] >= 256:
                raise Rejected("Observation allowance exhausted; do not reset the run")
            db.execute("INSERT INTO observations VALUES(?,?,?,?)", (probe_id, value_hash, canonical(packet).decode(), probe["observed_at"]))
            if db.execute("SELECT 1 FROM outbox").fetchone():
                return {"state": "coalesced", "reason": "one_admission_per_run"}
            rows = db.execute("SELECT value FROM observations WHERE observed_at>=? AND observed_at<=? ORDER BY observed_at,id LIMIT 64",
                              (probe["observed_at"] - 120, probe["observed_at"])).fetchall()
            compatible = [json.loads(row["value"]) for row in rows]
            policy_keys = ("uid", "generation", "observed_generation", "policy_spec_sha256", "policy_revision", "image_pattern", "observation_method")
            compatible = [v for v in compatible if all(v["policy"].get(k) == policy.get(k) for k in policy_keys) and v["rollout"]["uid"] == rollout["uid"]
                          and v["rollout"]["generation"] == rollout["generation"]]
            selected = next((v for v in reversed(list(itertools.combinations(compatible, 3)))
                             if 60 <= v[-1]["probe"]["observed_at"] - v[0]["probe"]["observed_at"] <= 120), None)
            if not selected:
                return {"state": "observing", "distinct_compatible_denials": len(compatible)}
            ids = sorted({item["probe"]["probe_id"] for item in selected} | {item["rollout"]["event_id"] for item in selected})
            candidate = {"schema_version": 1, "untrusted_evidence": True, "incident_id": c.incident_id, "run_id": c.run_id,
                         "profile_revision": c.profile_revision, "fingerprint": c.fingerprint, "cause": CAUSE,
                         "evidence_ids": ids, "observations": list(selected)}
            candidate_id = digest(candidate)
            candidate["candidate_id"] = candidate_id
            if len(canonical(candidate)) > MAX_CANDIDATE:
                raise Rejected("Candidate exceeds 16KiB; no classifier call allowed")
            db.execute("INSERT OR IGNORE INTO candidates VALUES(?,?,?)", (candidate_id, canonical(candidate).decode(), int(self.now())))
            self.ledger.patch({"phase": Phase.CANDIDATE.value, "candidate_id": candidate_id, "fingerprint": c.fingerprint}, db)
        return {"state": "candidate", "candidate_id": candidate_id, "evidence_ids": ids}

    def candidate(self, candidate_id):
        hash_value(candidate_id)
        with self.ledger.lock:
            row = self.ledger.db.execute("SELECT value FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if not row:
            raise Rejected("Unknown candidate identity")
        value = json.loads(row["value"])
        return Candidate(candidate_id, tuple(value["evidence_ids"]), value)

    def classify(self, candidate_id, callback):
        if not callable(callback):
            raise Rejected("An approved real-model callback is required; there is no fallback")
        candidate = self.candidate(candidate_id)
        if not all(self.now() - self.config.evidence_max_age_seconds <= p["probe"]["observed_at"] <= self.now() for p in candidate.packet["observations"]):
            raise Rejected("Candidate evidence is stale; no model call allowed")
        with self.ledger.transaction() as db:
            previous = db.execute("SELECT * FROM classifications WHERE candidate_id=?", (candidate_id,)).fetchone()
            if previous:
                return {"state": previous["status"], "candidate_id": candidate_id,
                        "classification": json.loads(previous["value"]) if previous["value"] else None}
            if db.execute("SELECT 1 FROM outbox").fetchone():
                raise Rejected("The run already admitted an investigation")
            count = db.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
            if count >= MAX_CLASSIFICATIONS:
                raise Rejected("Classifier allowance exhausted; do not reset the run")
            # Reservation is irreversible, including crashes and unavailable models.
            db.execute("INSERT INTO classifications VALUES(?,?,?,NULL,?)", (candidate_id, count + 1, "unknown", int(self.now())))
        limits = {"max_input_bytes": MAX_CANDIDATE, "max_input_tokens": MAX_INPUT_TOKENS, "max_output_tokens": MAX_OUTPUT_TOKENS,
                  "request_ordinal": count + 1, "request_limit": MAX_CLASSIFICATIONS}
        try:
            envelope = callback(json.loads(canonical(candidate.packet)), limits)
            exact(envelope, ("request_id", "model", "usage", "result"))
            ident(envelope["request_id"])
            ident(envelope["model"])
            exact(envelope["usage"], ("input_tokens", "output_tokens"))
            integer(envelope["usage"]["input_tokens"], 0, MAX_INPUT_TOKENS)
            integer(envelope["usage"]["output_tokens"], 0, MAX_OUTPUT_TOKENS)
            result = envelope["result"]
            exact(result, ("choice", "severity", "confidence", "cause", "evidence_ids"))
            if (result["choice"] not in {"investigate", "ignore", "unverified"}
                    or result["severity"] not in {"critical", "high", "medium", "low", "unknown"}
                    or type(result["confidence"]) not in {float, int} or not math.isfinite(result["confidence"])
                    or not 0 <= result["confidence"] <= 1 or result["cause"] != CAUSE
                    or not isinstance(result["evidence_ids"], list) or sorted(result["evidence_ids"]) != sorted(candidate.evidence_ids)):
                raise Rejected("Classifier returned an invalid or differently scoped decision")
            status = "accepted" if result["choice"] == "investigate" and result["severity"] == "critical" and result["confidence"] >= 0.95 else "suppressed"
        except Exception as error:
            self.ledger.patch({"classifier_health": "unverified", "classifier_error": type(error).__name__})
            return {"state": "unknown", "candidate_id": candidate_id, "reason": "classifier_unavailable_or_invalid"}
        with self.ledger.transaction() as db:
            prior = db.execute("SELECT value FROM classifications WHERE value IS NOT NULL").fetchall()
            if any(json.loads(row["value"])["request_id"] == envelope["request_id"] for row in prior):
                self.ledger.patch({"classifier_health": "unverified", "classifier_error": "ReusedRequestId"}, db)
                return {"state": "unknown", "candidate_id": candidate_id, "reason": "classifier_request_id_reused"}
            db.execute("UPDATE classifications SET status=?,value=? WHERE candidate_id=?", (status, canonical(envelope).decode(), candidate_id))
            self.ledger.patch({"phase": Phase.CLASSIFIED.value if status == "accepted" else Phase.OBSERVING.value,
                               "classifier_health": "observed", "accepted_candidate_id": candidate_id if status == "accepted" else None,
                               "classifier_confidence_is_calibrated": False}, db)
        return {"state": status, "candidate_id": candidate_id, "classification": envelope}

    def dispatch(self, callback):
        if not callable(callback):
            raise Rejected("An actual native-dispatch callback is required")
        with self.ledger.transaction() as db:
            existing = db.execute("SELECT * FROM outbox WHERE id=1").fetchone()
            if existing:
                status = existing["status"]
                if status == "pending":
                    status = "unknown"
                    db.execute("UPDATE outbox SET status='unknown' WHERE id=1")
                    self.ledger.patch({"phase": Phase.DISPATCH_UNKNOWN.value}, db)
                return {"state": status, **json.loads(existing["value"])}
            state = self.ledger.state(db)
            candidate_id = state.get("accepted_candidate_id")
            row = db.execute("SELECT * FROM classifications WHERE candidate_id=? AND status='accepted'", (candidate_id,)).fetchone()
            if not row:
                raise Rejected("No actual classifier decision admitted this run")
            candidate = self.candidate(candidate_id)
            if not all(self.now() - self.config.evidence_max_age_seconds <= p["probe"]["observed_at"] <= self.now() for p in candidate.packet["observations"]):
                raise Rejected("Admitted evidence is stale; do not dispatch a new native task")
            envelope = json.loads(row["value"])
            message_id = "kyverno-" + digest([self.config.run_id, self.config.fingerprint])[:32]
            value = {"message_id": message_id, "run_id": self.config.run_id, "incident_id": self.config.incident_id,
                     "fingerprint": self.config.fingerprint, "candidate_id": candidate_id, "classification_request_id": envelope["request_id"]}
            db.execute("INSERT INTO outbox VALUES(1,?,'pending',?)", (message_id, canonical(value).decode()))
            self.ledger.patch({"phase": Phase.DISPATCH_PENDING.value}, db)
        # Pending and original message ID are on disk before the external call.
        with self.ledger.transaction() as db:
            db.execute("UPDATE outbox SET status='unknown' WHERE id=1")
            self.ledger.patch({"phase": Phase.DISPATCH_UNKNOWN.value}, db)
        try:
            receipt = callback(dict(value))
            return self.reconcile_dispatch(receipt)
        except Exception as error:
            self.ledger.patch({"dispatch_error": type(error).__name__})
            return {"state": "unknown", **value, "reason": "reconcile_original_message_id_before_any_new_delivery"}

    def reconcile_dispatch(self, receipt):
        exact(receipt, ("message_id", "task_id", "task_state"))
        ident(receipt["message_id"])
        ident(receipt["task_id"])
        if receipt["task_state"] not in {"SUBMITTED", "WORKING", "INPUT_REQUIRED", "COMPLETED"}:
            raise Rejected("Native task receipt does not establish acceptance")
        with self.ledger.transaction() as db:
            row = db.execute("SELECT * FROM outbox WHERE id=1").fetchone()
            if not row or row["message_id"] != receipt["message_id"]:
                raise Rejected("Receipt does not match the durable original message identity")
            value = json.loads(row["value"])
            if value.get("task_id") and value["task_id"] != receipt["task_id"]:
                raise Rejected("Original message already binds a different native task")
            value.update(receipt)
            db.execute("UPDATE outbox SET status='accepted',value=? WHERE id=1", (canonical(value).decode(),))
            current = self.ledger.state(db)
            patch = {"native_task_id": receipt["task_id"], "native_message_id": receipt["message_id"]}
            if current["phase"] in {Phase.DISPATCH_PENDING.value, Phase.DISPATCH_UNKNOWN.value}:
                patch["phase"] = Phase.INVESTIGATING.value
            self.ledger.patch(patch, db)
        return {"state": "accepted", **value}

    def state(self):
        with self.ledger.lock:
            reservations = self.ledger.db.execute("SELECT candidate_id,ordinal,status,reserved_at FROM classifications ORDER BY ordinal").fetchall()
            row = self.ledger.db.execute("SELECT * FROM outbox WHERE id=1").fetchone()
            counts = {r["key"]: r["value"] for r in self.ledger.db.execute("SELECT * FROM counters")}
        return {"state": self.ledger.state(), "classifier_requests_reserved": len(reservations), "classifier_request_limit": MAX_CLASSIFICATIONS,
                "reserved_input_token_ceiling": len(reservations) * MAX_INPUT_TOKENS,
                "reserved_output_token_ceiling": len(reservations) * MAX_OUTPUT_TOKENS,
                "classifications": [dict(r) for r in reservations], "counters": counts,
                "outbox": {"status": row["status"], **json.loads(row["value"])} if row else None}
