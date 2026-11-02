"""Run with python3 runtime.py --config /config/config.json --data /data.

Real fixed-scope HTTP APIs only. The service never invokes a model or writes to
Kubernetes. Native requireApproval is configured independently by the operator.
"""
import argparse
import base64
import copy
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, build_opener
import uuid

from admission import Admission
from core import (APIError, FAULTY_PATTERN, HEALTHY_PATTERN, MAX_INPUT, MAX_OUTPUT, POLICY_OBSERVATION_METHOD,
                  Config, HTTPJSON, Ledger, NoRedirect, Phase, Rejected, Telemetry,
                  TraceContext, canonical, digest, exact, git_sha, hash_value,
                  ident, integer, validate_policy_bracket)


def image_pattern(policy):
    try:
        return policy["spec"]["rules"][0]["validate"]["pattern"]["spec"]["containers"][0]["image"]
    except (KeyError, TypeError, IndexError):
        raise Rejected("Configured policy does not have the permitted image-pattern field") from None


def policy_document(policy, config, expected_hash=None):
    try:
        valid = (isinstance(policy, dict) and policy["apiVersion"] == "kyverno.io/v1" and policy["kind"] == "Policy"
                 and policy["metadata"]["name"] == config.policy_name and policy["metadata"]["namespace"] == config.namespace
                 and policy["metadata"]["annotations"]["pod-policies.kyverno.io/autogen-controllers"] == "none"
                 and policy["spec"]["background"] is False and len(policy["spec"]["rules"]) == 1
                 and policy["spec"]["rules"][0]["name"] == config.rule_name
                 and policy["spec"]["rules"][0]["validate"]["failureAction"] == "Enforce"
                 and len(policy["spec"]["rules"][0]["validate"]["pattern"]["spec"]["containers"]) == 1)
    except (KeyError, TypeError, IndexError):
        valid = False
    if not valid or (expected_hash and digest(policy) != expected_hash):
        raise Rejected("Policy is outside the exact reviewed JSON fixture")
    image_pattern(policy)
    return policy


def observed_generation(resource):
    status = resource.get("status", {})
    value = status.get("observedGeneration")
    if type(value) is int:
        return value
    values = [c["observedGeneration"] for c in status.get("conditions", [])
              if c.get("type") == "Ready" and c.get("status") == "True" and type(c.get("observedGeneration")) is int]
    return max(values) if values else None


def ready(resource):
    status = resource.get("status", {})
    return status.get("ready") is True or any(c.get("type") == "Ready" and c.get("status") == "True" for c in status.get("conditions", []))


def policy_read_metadata(policy, at):
    return {"uid": policy["metadata"]["uid"], "generation": policy["metadata"]["generation"],
            "policy_spec_sha256": digest(policy["spec"]), "ready": ready(policy),
            "deleting": bool(policy["metadata"].get("deletionTimestamp")),
            "enforcement": policy["spec"]["rules"][0]["validate"]["failureAction"], "observed_at": int(at)}


class Runtime:
    def __init__(self, config, ledger, gitlab=None, kube=None, telemetry=None, now=time.time, human_merger_ids=()):
        self.config = Config.from_dict(config) if isinstance(config, dict) else config
        self.ledger, self.now = ledger, now
        self.lock = threading.RLock()
        if not isinstance(human_merger_ids, tuple):
            raise Rejected("Dashboard human IDs must be an explicit distinct tuple")
        for principal in human_merger_ids:
            integer(principal, 1)
        if len(set(human_merger_ids)) != len(human_merger_ids):
            raise Rejected("Dashboard human IDs must be distinct")
        self.human_merger_ids = human_merger_ids
        self.dashboard_merge_enabled = bool(human_merger_ids)
        c = self.config
        self.gitlab = gitlab or HTTPJSON("GitLab", c.gitlab_api, os.environ.get("GITLAB_TOKEN_FILE", "/gitlab/gitlab.token"))
        self.kube = kube or HTTPJSON("Kubernetes", c.kubernetes_api,
                                    "/var/run/secrets/kubernetes.io/serviceaccount/token",
                                    "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt", read_only=True)
        self.telemetry = telemetry or Telemetry(c, ledger)
        self.local = threading.local()
        self.probe_opener = build_opener(NoRedirect())

    def _gl(self, path, method="GET", body=None):
        carrier = getattr(self.local, "carrier", None)
        return self.gitlab.request("/projects/" + self.config.project_id + path, method, body, carrier)

    def _kube(self, path):
        return self.kube.request(path, traceparent=getattr(self.local, "carrier", None))

    def _branch_head(self, branch):
        branch_info = self._gl("/repository/branches/" + quote(branch, safe=""))
        if branch_info.get("name") != branch:
            raise Rejected("GitLab returned a different branch")
        return git_sha(branch_info["commit"]["id"])

    def _manifest(self, ref):
        f = self._gl("/repository/files/" + quote(self.config.policy_file, safe="") + "?" + urlencode({"ref": ref}))
        if f.get("file_path") != self.config.policy_file or f.get("encoding") != "base64":
            raise Rejected("GitLab returned a different policy file")
        try:
            raw = base64.b64decode(f["content"], validate=False)
            if len(raw) > 32768:
                raise Rejected("Policy file exceeds limit")
            policy = json.loads(raw)
        except (KeyError, ValueError, TypeError):
            raise Rejected("Policy file must contain bounded JSON") from None
        policy_document(policy, self.config)
        return policy, git_sha(f["last_commit_id"])

    def _policy(self):
        c = self.config
        return self._kube("/apis/kyverno.io/v1/namespaces/" + c.namespace + "/policies/" + c.policy_name)

    def _deployment(self):
        c = self.config
        d = self._kube("/apis/apps/v1/namespaces/" + c.namespace + "/deployments/" + c.application)
        m, spec, status = d["metadata"], d["spec"], d.get("status", {})
        return {"namespace": c.namespace, "deployment_name": c.application, "uid": m["uid"], "generation": m["generation"],
                "revision": m.get("annotations", {}).get("deployment.kubernetes.io/revision"),
                "observed_generation": status.get("observedGeneration"), "desired_replicas": spec.get("replicas", 1),
                "actual_replicas": status.get("replicas", 0), "updated_replicas": status.get("updatedReplicas", 0),
                "ready_replicas": status.get("readyReplicas", 0), "available_replicas": status.get("availableReplicas", 0),
                "unavailable_replicas": status.get("unavailableReplicas", 0), "strategy": spec.get("strategy", {}).get("type"),
                "images": [v.get("image") for v in spec["template"]["spec"]["containers"][:4]],
                "deleting": bool(m.get("deletionTimestamp")), "observed_at": int(self.now())}

    def read_kyverno_incident(self):
        c = self.config
        policy, deployment = self._policy(), self._deployment()
        selector = urlencode({"labelSelector": "app.kubernetes.io/name=" + c.application, "limit": 12})
        sets = self._kube("/apis/apps/v1/namespaces/" + c.namespace + "/replicasets?" + selector)
        pods = self._kube("/api/v1/namespaces/" + c.namespace + "/pods?" + selector)
        rs = [v for v in sets.get("items", []) if any(o.get("uid") == deployment["uid"] and o.get("kind") == "Deployment"
                                                         for o in v["metadata"].get("ownerReferences", []))]
        if deployment["revision"]:
            rs = [v for v in rs if v["metadata"].get("annotations", {}).get("deployment.kubernetes.io/revision") == deployment["revision"]]
        rs_ids = {v["metadata"]["uid"] for v in rs}
        events = self._kube("/api/v1/namespaces/" + c.namespace + "/events?" + urlencode({"fieldSelector": "reason=FailedCreate", "limit": 50}))
        denials = []
        for event in events.get("items", []):
            message = str(event.get("message", ""))
            if event.get("involvedObject", {}).get("uid") not in rs_ids or event.get("reason") != "FailedCreate":
                continue
            def mentions(name):
                return re.findall(r"(?<![A-Za-z0-9_.-])" + re.escape(name) + r"(?![A-Za-z0-9_.-])", message)
            if (not mentions(c.policy_name) or not mentions(c.rule_name)
                    or (c.policy_name == c.rule_name and len(mentions(c.policy_name)) < 2)):
                continue
            denials.append({"event_id": event["metadata"]["uid"], "reason": "FailedCreate", "policy_name": c.policy_name,
                            "rule_name": c.rule_name, "involved_uid": event["involvedObject"]["uid"],
                            "count": event.get("count", 1), "last_timestamp": event.get("lastTimestamp"),
                            "message": re.sub(r"[\x00-\x1f\x7f]", " ", message)[:400]})
        owned_pods = [p for p in pods.get("items", []) if any(o.get("uid") in rs_ids for o in p["metadata"].get("ownerReferences", []))]
        return {"mode": "live", "incident_id": c.incident_id, "run_id": c.run_id, "cluster_id": c.cluster_id,
                "policy": {"name": c.policy_name, "rule_name": c.rule_name, "uid": policy["metadata"]["uid"],
                           "generation": policy["metadata"]["generation"], "observed_generation": observed_generation(policy),
                           "ready": ready(policy), "image_pattern": image_pattern(policy), "policy_spec_sha256": digest(policy["spec"])},
                "deployment": deployment,
                "replicasets": [{"name": v["metadata"]["name"], "uid": v["metadata"]["uid"], "replicas": v.get("status", {}).get("replicas", 0)} for v in rs[:6]],
                "pods": [{"name": p["metadata"]["name"], "uid": p["metadata"]["uid"], "phase": p.get("status", {}).get("phase"),
                          "ready": any(v.get("type") == "Ready" and v.get("status") == "True" for v in p.get("status", {}).get("conditions", []))} for p in owned_pods[:6]],
                "failed_create": denials[-4:], "list_truncated": any(v.get("metadata", {}).get("continue") for v in (sets, pods, events)),
                "admission": {key: self.ledger.state().get(key) for key in ("phase", "candidate_id", "fingerprint", "native_task_id")}}

    def read_policy_repository(self):
        c = self.config
        head = self._branch_head(c.target_branch)
        policy, file_sha = self._manifest(head)
        return {"mode": "live", "project_id": c.project_id, "policy_file": c.policy_file, "target_branch": c.target_branch,
                "head_sha": head, "file_last_commit_sha": file_sha, "image_pattern": image_pattern(policy),
                "policy_sha256": digest(policy), "policy_spec_sha256": digest(policy["spec"]),
                "known_faulty_file": digest(policy) == c.faulty_policy_sha256,
                "healthy_pattern": HEALTHY_PATTERN, "policy": policy}

    def _valid_diffs(self, diffs):
        return (isinstance(diffs, list) and len(diffs) == 1 and diffs[0].get("old_path") == diffs[0].get("new_path") == self.config.policy_file
                and not any(diffs[0].get(k) for k in ("new_file", "renamed_file", "deleted_file", "collapsed", "too_large")))

    def _commit_from_branch(self, intent):
        try:
            head = self._branch_head(self.config.fix_branch)
        except APIError as error:
            if error.status == 404:
                return None
            raise
        commit = self._gl("/repository/commits/" + head)
        candidate, _ = self._manifest(head)
        diffs = self._gl("/repository/commits/" + head + "/diff?per_page=2")
        if (commit.get("parent_ids") != [intent["base_sha"]] or commit.get("title") != intent["commit_title"]
                or digest(candidate) != self.config.healthy_policy_sha256 or not self._valid_diffs(diffs)):
            raise Rejected("Existing fix branch is not the exact journalled commit; no adoption or retry")
        return {"head_sha": head}

    def _find_mr(self, head):
        c = self.config
        records = self._gl("/merge_requests?" + urlencode({"state": "all", "source_branch": c.fix_branch, "target_branch": c.target_branch, "per_page": 2}))
        if not isinstance(records, list) or len(records) > 1:
            raise Rejected("Ambiguous fixed-branch merge request identity")
        if not records:
            return None
        mr = records[0]
        if (mr.get("sha") != head or mr.get("source_branch") != c.fix_branch or mr.get("target_branch") != c.target_branch
                or str(mr.get("source_project_id")) != c.project_id or str(mr.get("target_project_id")) != c.project_id):
            raise Rejected("Merge request does not match the fixed project, branches and head")
        return {"iid": integer(mr["iid"], 1), "head_sha": head, "url": mr.get("web_url", "")}

    def _proposal(self, create=False, reason=None):
        c = self.config
        state = self.ledger.state()
        if state.get("proposal"):
            return state["proposal"]
        op = self.ledger.operation("policy-fix-commit")
        if not op:
            if not create:
                return None
            head = self._branch_head(c.target_branch)
            baseline, file_sha = self._manifest(head)
            policy_document(baseline, c, c.faulty_policy_sha256)
            if image_pattern(baseline) != FAULTY_PATTERN:
                raise Rejected("Target does not contain the exact known faulty pattern")
            expected = copy.deepcopy(baseline)
            expected["spec"]["rules"][0]["validate"]["pattern"]["spec"]["containers"][0]["image"] = HEALTHY_PATTERN
            if digest(expected) != c.healthy_policy_sha256 or digest(expected["spec"]) != c.healthy_policy_spec_sha256:
                raise Rejected("Configured healthy hashes do not match the single permitted field change")
            try:
                self._branch_head(c.fix_branch)
            except APIError as error:
                if error.status != 404:
                    raise
            else:
                raise Rejected("Fix branch already exists without this run's durable intent")
            intent = {"base_sha": head, "base_file_sha": file_sha, "commit_title": "Repair approved registry [" + c.run_id + "]",
                      "reason": reason, "faulty_hash": c.faulty_policy_sha256, "healthy_hash": c.healthy_policy_sha256}
            if not self.ledger.reserve_operation("policy-fix-commit", "gitlab_create_commit", intent):
                raise Rejected("Concurrent proposal intent; reconcile the existing operation")
            try:
                commit = self._gl("/repository/commits", "POST", {"branch": c.fix_branch, "start_sha": head,
                                  "commit_message": intent["commit_title"], "actions": [{"action": "update", "file_path": c.policy_file,
                                  "content": json.dumps(expected, indent=2) + "\n"}]})
                receipt = self._commit_from_branch(intent)
                if not receipt or commit.get("id") != receipt["head_sha"]:
                    raise Rejected("Commit write lacks an exact read-back receipt")
                self.ledger.resolve_operation("policy-fix-commit", receipt)
            except (APIError, OSError):
                return {"state": "unknown", "operation": "policy-fix-commit", "reason": "reconcile_fixed_branch_before_any_retry"}
            op = self.ledger.operation("policy-fix-commit")
        if op["status"] != "confirmed":
            receipt = self._commit_from_branch(op["intent"])
            if not receipt:
                return {"state": "unknown", "operation": "policy-fix-commit", "reason": "no_confirmed_write_outcome_no_retry"}
            self.ledger.resolve_operation("policy-fix-commit", receipt)
            op = self.ledger.operation("policy-fix-commit")
        head, intent = op["receipt"]["head_sha"], op["intent"]
        mr_op = self.ledger.operation("policy-fix-mr")
        if not mr_op:
            if self._find_mr(head):
                raise Rejected("MR exists without this run's durable creation intent")
            if not create:
                return {"state": "commit_confirmed", "head_sha": head, "mr": "not_requested"}
            if not self.ledger.reserve_operation("policy-fix-mr", "gitlab_create_mr", {"head_sha": head, "base_sha": intent["base_sha"]}):
                raise Rejected("Concurrent MR intent; reconcile the existing operation")
            try:
                self._gl("/merge_requests", "POST", {"source_branch": c.fix_branch, "target_branch": c.target_branch,
                         "title": intent["commit_title"], "description": intent["reason"] + "\n\nExact-head CI, independent native review, and human approval are required. Review and merge in GitLab. Flux owns policy delivery. Live recovery must be verified after merge before ticket closure.",
                         "remove_source_branch": False, "squash": False})
            except (APIError, OSError):
                return {"state": "unknown", "operation": "policy-fix-mr", "reason": "reconcile_fixed_mr_identity_before_any_retry"}
            mr_op = self.ledger.operation("policy-fix-mr")
        mr = self._find_mr(head)
        if not mr:
            return {"state": "unknown", "operation": "policy-fix-mr", "reason": "no_confirmed_write_outcome_no_retry"}
        self.ledger.resolve_operation("policy-fix-mr", mr)
        binding = {"project_id": c.project_id, "iid": mr["iid"], "head_sha": head, "base_sha": intent["base_sha"],
                   "base_file_sha": intent["base_file_sha"], "incident_id": c.incident_id, "run_id": c.run_id}
        proposal = {"binding": binding, "url": mr["url"], "created_at": int(self.now())}
        self.ledger.patch({"proposal": proposal, "phase": Phase.PROPOSED.value})
        return proposal

    def propose_policy_fix(self, reason, image_pattern):
        if (not isinstance(reason, str) or not 10 <= len(reason) <= 1000 or re.search(r"[\x00-\x08\x0b-\x1f\x7f]", reason)
                or image_pattern != HEALTHY_PATTERN):
            raise Rejected("Require an evidence-based reason and the single reviewed healthy image pattern")
        with self.lock:
            proposal = self._proposal(create=True, reason=reason)
            if not proposal or "binding" not in proposal:
                return proposal or {"state": "unknown"}
            return self.inspect_policy_fix()

    def _ci(self, head):
        c = self.config
        pipelines = self._gl("/pipelines?" + urlencode({"sha": head, "order_by": "id", "sort": "desc", "per_page": 1}))
        if not isinstance(pipelines, list) or not pipelines:
            return {"ci_pass": False, "pipeline": None, "jobs": [], "tests": [], "test_metadata": "waiting"}
        pipeline_id = integer(pipelines[0]["id"], 1)
        pipeline = self._gl("/pipelines/" + str(pipeline_id))
        if pipeline.get("sha") != head:
            raise Rejected("Pipeline response does not match the exact MR head")
        jobs = self._gl("/pipelines/" + str(pipeline_id) + "/jobs?per_page=100&include_retried=false")
        if not isinstance(jobs, list) or len(jobs) >= 100:
            raise Rejected("Job result is truncated or invalid")
        selected_jobs = [{"name": j.get("name"), "status": j.get("status"), "id": j.get("id")} for j in jobs if j.get("name") in c.required_ci_jobs]
        tests, metadata = [], "observed"
        try:
            report = self._gl("/pipelines/" + str(pipeline_id) + "/test_report?per_page=100")
            for suite in report.get("test_suites", []):
                for case in suite.get("test_cases", []):
                    if case.get("name") in c.required_test_cases:
                        tests.append({"name": case["name"], "status": case.get("status")})
        except APIError:
            metadata = "unavailable"
        jobs_pass = all(sum(j["name"] == name and j["status"] == "success" for j in selected_jobs) == 1
                        and sum(j["name"] == name for j in selected_jobs) == 1 for name in c.required_ci_jobs)
        tests_pass = all(sum(t["name"] == name and t["status"] == "success" for t in tests) == 1
                         and sum(t["name"] == name for t in tests) == 1 for name in c.required_test_cases)
        return {"ci_pass": pipeline.get("status") == "success" and jobs_pass and tests_pass,
                "pipeline": {k: pipeline.get(k) for k in ("id", "sha", "status", "ref", "source", "updated_at")},
                "jobs": selected_jobs, "tests": tests, "test_metadata": metadata}

    def inspect_policy_fix(self):
        with self.lock:
            proposal = self._proposal(create=False)
            if not proposal or "binding" not in proposal:
                return proposal or {"state": "not_proposed"}
            c, b = self.config, proposal["binding"]
            mr = self._gl("/merge_requests/" + str(b["iid"]))
            if (mr.get("sha") != b["head_sha"] or mr.get("source_branch") != c.fix_branch or mr.get("target_branch") != c.target_branch
                    or str(mr.get("source_project_id")) != c.project_id or str(mr.get("target_project_id")) != c.project_id):
                raise Rejected("MR head/project/branches changed; existing review and approval cannot be used")
            candidate, _ = self._manifest(b["head_sha"])
            baseline, _ = self._manifest(b["base_sha"])
            diffs = self._gl("/merge_requests/" + str(b["iid"]) + "/diffs?per_page=2")
            expected = copy.deepcopy(baseline)
            expected["spec"]["rules"][0]["validate"]["pattern"]["spec"]["containers"][0]["image"] = HEALTHY_PATTERN
            valid = (digest(baseline) == c.faulty_policy_sha256 and digest(candidate) == c.healthy_policy_sha256
                     and candidate == expected and self._valid_diffs(diffs))
            state = self.ledger.state()
            return {"binding": b, "url": proposal["url"], "state": mr.get("state"), "draft": bool(mr.get("draft", mr.get("work_in_progress", False))),
                    "diff_valid": valid, "diff": [{"file": d.get("new_path"), "patch": str(d.get("diff", ""))[:2200]} for d in diffs[:2]],
                    "from_pattern": FAULTY_PATTERN, "to_pattern": HEALTHY_PATTERN, "policy_spec_sha256": digest(candidate["spec"]),
                    "merge_status": mr.get("detailed_merge_status"), "merge_commit_sha": mr.get("merge_commit_sha"),
                    "merged_at": mr.get("merged_at"), **self._ci(b["head_sha"]),
                    "review": state.get("review"), "native_approval_request": state.get("native_approval_request"),
                    "human_authorization": state.get("human_authorization")}

    def _binding(self, value):
        b = self.ledger.state().get("proposal", {}).get("binding")
        if not b or value != b:
            raise Rejected("Use the exact recorded MR and head binding")
        return b

    def _merge_reconcile(self, binding):
        mr = self._gl("/merge_requests/" + str(binding["iid"]))
        c = self.config
        if (mr.get("sha") != binding["head_sha"] or mr.get("source_branch") != c.fix_branch or mr.get("target_branch") != c.target_branch
                or str(mr.get("source_project_id")) != c.project_id or str(mr.get("target_project_id")) != c.project_id):
            raise Rejected("MR changed during uncertain merge; independent reconciliation required")
        if mr.get("state") != "merged" or not mr.get("merge_commit_sha"):
            return {"state": "unknown", "operation": "policy-fix-merge", "reason": "uncertain_merge_no_automatic_retry"}
        receipt = {"binding": binding, "merge_sha": git_sha(mr["merge_commit_sha"]), "merged_at": mr.get("merged_at"),
                   "observed_at": int(self.now()), "url": mr.get("web_url", "")}
        self.ledger.resolve_operation("policy-fix-merge", receipt)
        self.ledger.patch({"merged": receipt, "phase": Phase.RECONCILING.value})
        return {"state": "merged", **receipt}

    def merge_policy_fix(self):
        with self.lock:
            state = self.ledger.state()
            b = state.get("proposal", {}).get("binding")
            if not b:
                raise Rejected("No proposal exists")
            if state.get("flow_dashboard_approval") or self.ledger.operation("flow-dashboard-merge"):
                raise Rejected("This run uses the dashboard-approved native merge path")
            if self.ledger.operation("policy-fix-merge"):
                return self._merge_reconcile(b)
            info = self.inspect_policy_fix()
            review, request, decision = (state.get(k, {}) for k in ("review", "native_approval_request", "human_authorization"))
            if (review.get("binding") != b or review.get("verdict") != "PASS" or review.get("reviewer_id") != self.config.reviewer_id
                    or not info["diff_valid"] or not info["ci_pass"] or info["draft"] or info["state"] != "opened"):
                raise Rejected("Exact diff, latest exact-head CI/tests and independent native review are required")
            if (request.get("binding") != b or decision.get("binding") != b or decision.get("decision") != "approved"
                    or decision.get("principal_type") != "human" or decision.get("principal_id") != self.config.human_approver_id
                    or not decision.get("decided_at", 0) <= self.now() < decision.get("expires_at", 0)
                    or any(request.get(k) != decision.get(k) for k in ("task_id", "approval_id", "tool_call_id", "tool_name"))
                    or request.get("task_id") != state.get("native_task_id")):
                raise Rejected("Actual native approval receipt and live independent exact-head human authorization are required")
            current_head = self._branch_head(self.config.target_branch)
            current, file_sha = self._manifest(current_head)
            if current_head != b["base_sha"] or file_sha != b["base_file_sha"] or digest(current) != self.config.faulty_policy_sha256:
                raise Rejected("Target changed after proposal; stop for a fresh run and review")
            if self._branch_head(self.config.fix_branch) != b["head_sha"]:
                raise Rejected("Source branch changed after review")
            if not self.ledger.reserve_operation("policy-fix-merge", "gitlab_merge_mr", {"binding": b, "approval_id": decision["approval_id"]}):
                raise Rejected("Concurrent merge intent; reconcile the existing operation")
            self.ledger.patch({"phase": Phase.MERGE_UNKNOWN.value})
            try:
                self._gl("/merge_requests/" + str(b["iid"]) + "/merge", "PUT", {"sha": b["head_sha"], "should_remove_source_branch": False})
            except (APIError, OSError):
                return {"state": "unknown", "operation": "policy-fix-merge", "reason": "reconcile_existing_mr_before_any_retry"}
            return self._merge_reconcile(b)

    def tool_enabled(self, name):
        return name != "merge_dashboard_approved_fix" or self.dashboard_merge_enabled

    def merge_dashboard_approved_fix(self):
        if not self.dashboard_merge_enabled:
            raise Rejected("Dashboard-approved native merge is disabled")
        from gitlab_lifecycle import Lifecycle
        return Lifecycle(self, self.human_merger_ids).merge_dashboard_approved_fix()

    def _http_probe(self):
        status, body, error = 0, b"", None
        try:
            try:
                response = self.probe_opener.open(Request(self.config.application_url, headers={"Accept": "text/plain"}), timeout=4)
            except HTTPError as exc:
                response = exc
            with response:
                status = response.code
                body = response.read(65537)
            if len(body) > 65536:
                error = "body_limit_exceeded"
        except (URLError, OSError):
            error = "http_unavailable"
        return {"probe_id": "http-" + uuid.uuid4().hex, "observed_at": int(self.now()), "status_code": status,
                "body_sha256": hashlib.sha256(body).hexdigest(), **({"error": error} if error else {})}

    def verify_recovery(self):
        with self.lock:
            state = self.ledger.state()
            if not state.get("merged"):
                return {"state": "waiting", "fixed": False, "reasons": ["No independently journalled merged receipt"]}
            info = self.inspect_policy_fix()
            merge_sha = state["merged"]["merge_sha"]
            if info.get("state") != "merged" or info.get("merge_commit_sha") != merge_sha:
                return {"state": "unknown", "fixed": False, "reasons": ["Current GitLab merge receipt does not match"]}
            c = self.config
            source = self._kube("/apis/source.toolkit.fluxcd.io/v1/namespaces/" + c.flux_namespace + "/gitrepositories/" + c.flux_source)
            flux = self._kube("/apis/kustomize.toolkit.fluxcd.io/v1/namespaces/" + c.flux_namespace + "/kustomizations/" + c.flux_kustomization)
            policy, deployment = self._policy(), self._deployment()
            policy_document(policy, c)
            current_before = policy_read_metadata(policy, self.now())
            generation, observed = policy["metadata"]["generation"], observed_generation(policy)
            spec_hash = digest(policy["spec"])
            probes = [self._http_probe() for _ in range(3)]
            source_revision = source.get("status", {}).get("artifact", {}).get("revision", "")
            applied_revision = flux.get("status", {}).get("lastAppliedRevision", "")
            def revision_sha(value):
                return value.rsplit(":", 1)[-1] if isinstance(value, str) else ""
            reasons = []
            if (revision_sha(source_revision) != merge_sha or revision_sha(applied_revision) != merge_sha or source_revision != applied_revision
                    or not ready(source) or not ready(flux)
                    or observed_generation(source) != source["metadata"].get("generation")
                    or observed_generation(flux) != flux["metadata"].get("generation")):
                reasons.append("Flux source/applied merge SHA and current Ready generations are not proven")
            policy_after = self._policy()
            policy_document(policy_after, c)
            current_after = policy_read_metadata(policy_after, self.now())
            if (spec_hash != c.healthy_policy_spec_sha256 or image_pattern(policy) != HEALTHY_PATTERN or not ready(policy)
                    or policy["metadata"].get("deletionTimestamp") or any(current_before[k] != current_after[k] for k in current_before if k != "observed_at")):
                reasons.append("Live healthy policy hash, enforcement and stable current identity are not proven")
            rollout_ok = (deployment["generation"] == deployment["observed_generation"] and deployment["strategy"] == "Recreate"
                          and not deployment["deleting"] and all(deployment[k] == 1 for k in
                          ("desired_replicas", "actual_replicas", "updated_replicas", "ready_replicas", "available_replicas"))
                          and deployment["unavailable_replicas"] == 0 and deployment["images"] == ["docker.io/library/busybox:1.36"])
            if not rollout_ok:
                reasons.append("Current single-replica application rollout is not recovered")
            if (len({p["probe_id"] for p in probes}) != 3 or not all(p["status_code"] == c.expected_http_status
                    and p["body_sha256"] == c.expected_body_sha256 and not p.get("error")
                    and self.now() - c.evidence_max_age_seconds <= p["observed_at"] <= self.now() for p in probes)):
                reasons.append("Three actual expected HTTP responses are not proven")
            receipt = state.get("probe_receipt", {})
            observations = receipt.get("observations", [])
            valid = [p for p in observations if p["kind"] == "valid" and p["result"] == "admitted"]
            invalid = [p for p in observations if p["kind"] == "invalid" and p["result"] == "denied"]
            fresh = (bool(observations) and all(self.now() - c.evidence_max_age_seconds <= p["observed_at"] <= self.now()
                                              and p["observed_at"] >= state["merged"]["observed_at"] for p in observations))
            method = "native-observed-generation"
            active_generation = None
            if observed != generation:
                method = receipt.get("observation_method", "unknown")
                try:
                    if observed is not None or method != POLICY_OBSERVATION_METHOD:
                        raise Rejected("No explicit active-admission proof variant")
                    validate_policy_bracket(receipt.get("policy_read_before"), receipt.get("policy_read_after"),
                                            policy["metadata"]["uid"], generation, spec_hash,
                                            [p["observed_at"] for p in observations], self.now(), c.evidence_max_age_seconds)
                    active_generation = generation
                except Rejected:
                    reasons.append("Current policy generation requires native status or an explicit stable-read admission-probe proof")
            if (receipt.get("merge_sha") != merge_sha or receipt.get("policy_uid") != policy["metadata"]["uid"]
                    or receipt.get("generation") != generation or receipt.get("observed_generation") != observed
                    or receipt.get("policy_spec_sha256") != spec_hash or not fresh or len(valid) < 3 or len(invalid) < 1
                    or len(valid) + len(invalid) != len(observations)):
                reasons.append("Fresh exact-policy positive and negative admission receipts are missing or incomplete")
            result = {"state": "verified" if not reasons else "waiting", "fixed": not reasons, "reasons": reasons,
                      "merge_sha": merge_sha, "source_revision": source_revision, "applied_revision": applied_revision,
                      "policy": {"uid": policy["metadata"]["uid"], "generation": generation, "observed_generation": observed,
                                 "policy_spec_sha256": spec_hash, "ready": ready(policy), "enforcement": "Enforce"},
                      "policy_observation_method": method, "active_probe_generation": active_generation,
                      "policy_read_before": receipt.get("policy_read_before"), "policy_read_after": receipt.get("policy_read_after"),
                      "current_policy_read_before": current_before, "current_policy_read_after": current_after,
                      "deployment": deployment, "http_observations": probes,
                      "probe_receipt_id": receipt.get("receipt_id"), "verified_at": int(self.now())}
            self.ledger.patch({"verification": result, "phase": Phase.VERIFIED.value if not reasons else Phase.RECONCILING.value})
            return result

    def _timestamp(self, value, age=300):
        integer(value, 1)
        if not self.now() - age <= value <= self.now():
            raise Rejected("Receipt is stale or from the future")

    def _record_once(self, key, value, phase=None):
        with self.ledger.transaction() as db:
            previous = self.ledger.state(db).get(key)
            if previous and previous != value:
                raise Rejected("An immutable receipt is already recorded")
            return self.ledger.patch({key: value, **({"phase": phase} if phase else {})}, db)

    def control(self, body):
        with self.lock:
            if not isinstance(body, dict):
                raise Rejected("Invalid control object")
            action = body.get("action")
            state = self.ledger.state()
            if action == "approve_dashboard":
                exact(body, ("action", "approval"))
                if not self.dashboard_merge_enabled:
                    raise Rejected("Dashboard approval is disabled")
                from gitlab_lifecycle import Lifecycle
                return Lifecycle(self, self.human_merger_ids).approve_dashboard(body["approval"])
            if action == "record_review":
                exact(body, ("action", "binding", "reviewer_id", "task_id", "task_state", "verdict", "native_receipt_sha256", "reviewed_at", "valid_admission", "invalid_admission"))
                b = self._binding(body["binding"])
                ident(body["task_id"])
                hash_value(body["native_receipt_sha256"])
                self._timestamp(body["reviewed_at"])
                info = self.inspect_policy_fix()
                if (body["reviewer_id"] != self.config.reviewer_id or body["task_id"] == state.get("native_task_id")
                        or body["task_state"] != "COMPLETED" or body["verdict"] != "PASS" or not info["ci_pass"]
                        or not info["diff_valid"] or body["valid_admission"] != "pass" or body["invalid_admission"] != "pass"):
                    raise Rejected("Independent completed native review must pass both admission checks at the exact CI head")
                self._record_once("review", {k: v for k, v in body.items() if k != "action"}, Phase.REVIEWED.value)
                return {"state": "reviewed", "binding": b}
            if action == "record_native_approval_request":
                exact(body, ("action", "binding", "task_id", "approval_id", "tool_call_id", "tool_name", "task_state", "native_receipt_sha256", "observed_at"))
                b = self._binding(body["binding"])
                for key in ("task_id", "approval_id", "tool_call_id"):
                    ident(body[key])
                hash_value(body["native_receipt_sha256"])
                self._timestamp(body["observed_at"])
                info = self.inspect_policy_fix()
                if (body["task_id"] != state.get("native_task_id") or body["task_state"] != "INPUT_REQUIRED"
                        or body["tool_name"] != "merge_policy_fix" or state.get("review", {}).get("binding") != b
                        or state["review"].get("verdict") != "PASS" or not info["diff_valid"] or not info["ci_pass"]):
                    raise Rejected("Actual native INPUT_REQUIRED request, tool-call binding and completed review are required")
                self._record_once("native_approval_request", {k: v for k, v in body.items() if k != "action"}, Phase.AWAITING_HUMAN.value)
                return {"state": "awaiting_human", "binding": b}
            if action == "authorize_merge":
                exact(body, ("action", "binding", "task_id", "approval_id", "tool_call_id", "tool_name", "decision", "principal_type", "principal_id", "native_receipt_sha256", "decided_at"))
                b = self._binding(body["binding"])
                request = state.get("native_approval_request", {})
                hash_value(body["native_receipt_sha256"])
                self._timestamp(body["decided_at"], 900)
                if (not request or any(body[k] != request.get(k) for k in ("task_id", "approval_id", "tool_call_id", "tool_name"))
                        or body["principal_type"] != "human" or body["principal_id"] != self.config.human_approver_id
                        or body["decision"] not in {"approved", "denied"} or body["decided_at"] < request["observed_at"]
                        or body["native_receipt_sha256"] == request["native_receipt_sha256"]):
                    raise Rejected("Require actual native human decision data matching the independently recorded approval request")
                info = self.inspect_policy_fix()
                if not info["diff_valid"] or not info["ci_pass"] or state.get("review", {}).get("binding") != b:
                    raise Rejected("Review and exact-head CI gates changed before human authorization")
                value = {k: v for k, v in body.items() if k != "action"}
                value["expires_at"] = body["decided_at"] + 900
                self._record_once("human_authorization", value, Phase.AUTHORIZED.value if body["decision"] == "approved" else Phase.AWAITING_HUMAN.value)
                return {"state": "authorized" if body["decision"] == "approved" else "declined", "binding": b}
            if action == "record_probe_receipt":
                exact(body, ("action", "receipt"))
                r = body["receipt"]
                exact(r, ("receipt_id", "run_id", "incident_id", "source", "source_receipt_sha256", "merge_sha", "policy_uid", "generation", "observed_generation", "policy_spec_sha256", "observations"),
                      ("observation_method", "policy_read_before", "policy_read_after"))
                for key in ("receipt_id", "policy_uid"):
                    ident(r[key])
                for key in ("source_receipt_sha256", "policy_spec_sha256"):
                    hash_value(r[key])
                git_sha(r["merge_sha"])
                integer(r["generation"], 1)
                if r["observed_generation"] is not None:
                    integer(r["observed_generation"], 1)
                if r["run_id"] != self.config.run_id or r["incident_id"] != self.config.incident_id or r["source"] != "operator-kubernetes-dry-run":
                    raise Rejected("Probe receipt is outside this run or approved probe source")
                if not isinstance(r["observations"], list) or not 1 <= len(r["observations"]) <= 16:
                    raise Rejected("Invalid bounded probe observations")
                ids = set()
                for p in r["observations"]:
                    exact(p, ("probe_id", "observed_at", "kind", "result", "policy_name", "rule_name"))
                    ident(p["probe_id"])
                    self._timestamp(p["observed_at"])
                    if (p["probe_id"] in ids or p["kind"] not in {"valid", "invalid"} or p["result"] not in {"admitted", "denied", "error"}
                            or p["policy_name"] != self.config.policy_name or p["rule_name"] != self.config.rule_name):
                        raise Rejected("Invalid or differently scoped probe evidence")
                    ids.add(p["probe_id"])
                if r["observed_generation"] is None:
                    if r.get("observation_method") != POLICY_OBSERVATION_METHOD:
                        raise Rejected("Missing native observed generation requires the explicit active-admission proof variant")
                    validate_policy_bracket(r.get("policy_read_before"), r.get("policy_read_after"), r["policy_uid"], r["generation"], r["policy_spec_sha256"],
                                            [p["observed_at"] for p in r["observations"]], self.now(), self.config.evidence_max_age_seconds)
                identities = {"receipt:" + r["receipt_id"]: digest(r), **{"probe:" + p["probe_id"]: digest(p) for p in r["observations"]}}
                with self.ledger.transaction() as db:
                    for key, value in identities.items():
                        previous = db.execute("SELECT payload_hash FROM receipt_identities WHERE id=?", (key,)).fetchone()
                        if previous and previous["payload_hash"] != value:
                            raise Rejected("Probe receipt or probe ID reused with different evidence")
                    for key, value in identities.items():
                        db.execute("INSERT OR IGNORE INTO receipt_identities VALUES(?,?)", (key, value))
                    self.ledger.patch({"probe_receipt": r}, db)
                return {"state": "recorded", "receipt_id": r["receipt_id"]}
            raise Rejected("Unknown operator action")

    def invoke(self, name, arguments, context=None):
        if name not in TOOLS or not self.tool_enabled(name):
            raise Rejected("Unknown fixed tool")
        schema = TOOLS[name][1]
        exact(arguments, schema["required"])
        context = context or TraceContext.incoming()
        if name == "merge_dashboard_approved_fix":
            binding = self.ledger.state().get("flow_merge_task_binding") or {}
            if binding and context.task_id and context.task_id != binding.get("task_id"):
                raise Rejected("Native merge task differs from the operator-bound task")
        span, started, failed = uuid.uuid4().hex[:16], time.time_ns(), False
        self.local.carrier = "00-" + context.trace_id + "-" + span + "-01"
        try:
            result = getattr(self, name)(**arguments)
            if len(canonical(result)) > MAX_OUTPUT - 2200:
                raise Rejected("Tool result exceeds 8KiB envelope budget")
            return result
        except Exception:
            failed = True
            raise
        finally:
            system = "kubernetes" if name in {"read_kyverno_incident", "verify_recovery"} else "gitlab"
            service = self.config.kubernetes_service if system == "kubernetes" else self.config.gitlab_service
            self.telemetry.export(service, context, span, "MCP " + name, started, failed,
                                  {"gen_ai.tool.name": name, "mcp.tool.name": name, "flow.tool.system": system})
            self.local.carrier = None

    def public_state(self):
        value = Admission(self.config, self.ledger, self.now).state()
        # Operator reads metadata only; exact candidate data is available through
        # the imported Admission API instead of an unbounded HTTP state dump.
        if len(canonical(value)) > MAX_OUTPUT - 100:
            state = value["state"]
            for key in ("verification", "probe_receipt"):
                if key in state:
                    state[key] = {k: v for k, v in state[key].items() if k not in {"observations", "http_observations"}}
        if len(canonical(value)) > MAX_OUTPUT - 100:
            raise Rejected("State exceeds bounded response; inspect durable ledger locally")
        return value


EMPTY_SCHEMA = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
PROPOSE_SCHEMA = {"type": "object", "properties": {"reason": {"type": "string", "minLength": 10, "maxLength": 1000},
                  "image_pattern": {"type": "string", "enum": [HEALTHY_PATTERN]}}, "required": ["reason", "image_pattern"], "additionalProperties": False}
TOOLS = {
    "read_kyverno_incident": ("Read the exact live namespaced policy, application rollout and owned FailedCreate evidence.", EMPTY_SCHEMA, True),
    "read_policy_repository": ("Read the fixed GitLab policy JSON and current branch/file revisions.", EMPTY_SCHEMA, True),
    "propose_policy_fix": ("Create at most one exact-head MR replacing only docker.io/libary/* with docker.io/library/*. Never applies or merges.", PROPOSE_SCHEMA, False),
    "inspect_policy_fix": ("Inspect the recorded exact MR head, single-file diff, latest head CI/JUnit cases and independent receipts.", EMPTY_SCHEMA, True),
    "merge_policy_fix": ("Merge only the exact recorded MR after native requireApproval AND independent operator-ledger human authorization. Never self-approve.", EMPTY_SCHEMA, False),
    "merge_dashboard_approved_fix": ("Merge the exact recorded repair MR only after durable dashboard human approval and independent review/CI. Never records approval.", EMPTY_SCHEMA, False),
    "verify_recovery": ("Read live Flux/policy/rollout, perform three HTTP probes and join actual operator admission receipts; missing evidence remains waiting.", EMPTY_SCHEMA, True),
}
REVIEWER_TOOLS = frozenset({"read_kyverno_incident", "read_policy_repository", "inspect_policy_fix"})


class Handler(BaseHTTPRequestHandler):
    server_version = "ScopedKyverno/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def _role(self):
        auth = self.headers.get("Authorization", "")
        return next((role for role, token in self.server.tokens.items() if hmac.compare_digest(auth, "Bearer " + token)), None)

    def _reply(self, status, payload):
        data = canonical(payload)
        if len(data) > MAX_OUTPUT:
            status, data = 500, b'{"error":"Response exceeds bounded transport limit"}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/healthz":
            return self._reply(200, {"ok": True, "mode": "live-scoped-adapter"})
        if self.path != "/state":
            return self._reply(404, {"error": "Unknown route"})
        if self._role() != "operator":
            return self._reply(401, {"error": "Unauthorized"})
        try:
            return self._reply(200, self.server.runtime.public_state())
        except Rejected:
            return self._reply(503, {"error": "State exceeds bounded transport; inspect the ledger locally"})

    def do_POST(self):
        role = self._role()
        route_role = {"/control": "operator", "/mcp/investigator": "investigator", "/mcp/reviewer": "reviewer"}.get(self.path)
        if not route_role:
            return self._reply(404, {"error": "Unknown route"})
        if role != route_role:
            return self._reply(401, {"error": "Unauthorized"})
        try:
            if self.headers.get("Transfer-Encoding"):
                raise Rejected("Chunked requests are unsupported")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_INPUT:
                raise Rejected("Invalid inbound limit")
            self.connection.settimeout(10)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise Rejected("Incomplete request")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise Rejected("Invalid object")
        except (ValueError, OSError):
            self.close_connection = True
            return self._reply(400, {"error": "Invalid or oversized request"})
        if self.path == "/control":
            try:
                return self._reply(200, self.server.runtime.control(payload))
            except (Rejected, KeyError, TypeError):
                return self._reply(409, {"error": "Control receipt rejected; exact actual native/operator data and gates are required"})
            except OSError:
                return self._reply(503, {"error": "Configured upstream is unavailable; no receipt was inferred"})
        try:
            exact(payload, ("jsonrpc", "method"), ("id", "params"))
            if payload["jsonrpc"] != "2.0" or not isinstance(payload["method"], str):
                raise Rejected("Invalid JSON-RPC")
            method, params = payload["method"], payload.get("params", {})
            if not isinstance(params, dict):
                raise Rejected("Invalid params")
            if "id" not in payload and method.startswith("notifications/"):
                return self._reply(202, {})
            if "id" not in payload or type(payload["id"]) not in {str, int}:
                raise Rejected("Missing bounded request identity")
            if isinstance(payload["id"], str) and len(payload["id"]) > 128:
                raise Rejected("Oversized request identity")
            if method == "initialize":
                version = params.get("protocolVersion", "2025-03-26")
                if version not in {"2024-11-05", "2025-03-26", "2025-06-18"}:
                    version = "2025-03-26"
                result = {"protocolVersion": version, "capabilities": {"tools": {}}, "serverInfo": {"name": "kyverno-" + role, "version": "1.0"}}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                names = TOOLS.keys() if role == "investigator" else REVIEWER_TOOLS
                result = {"tools": [{"name": n, "description": TOOLS[n][0], "inputSchema": TOOLS[n][1],
                                     "annotations": {"readOnlyHint": TOOLS[n][2], "destructiveHint": n in {"merge_policy_fix", "merge_dashboard_approved_fix"}, "idempotentHint": True}}
                                    for n in sorted(names) if self.server.runtime.tool_enabled(n)]}
            elif method == "tools/call":
                exact(params, ("name",), ("arguments", "_meta"))
                name, arguments = params["name"], params.get("arguments", {})
                if (name not in TOOLS or not self.server.runtime.tool_enabled(name)
                        or (role == "reviewer" and name not in REVIEWER_TOOLS)):
                    raise Rejected("Tool is outside this role")
                meta = params.get("_meta", {})
                if not isinstance(meta, dict):
                    raise Rejected("Invalid metadata")
                meta = {**meta}
                for header, key in (("X-Mcp-Tool-Call-Id", "tool_call_id"), ("X-Kagent-Task-Id", "task_id")):
                    if self.headers.get(header):
                        meta[key] = self.headers[header]
                context = TraceContext.incoming(self.headers.get("traceparent", ""), meta)
                try:
                    value = self.server.runtime.invoke(name, arguments, context)
                    result = {"content": [{"type": "text", "text": canonical(value).decode()}], "isError": False}
                except Rejected as error:
                    result = {"content": [{"type": "text", "text": str(error)[:300]}], "isError": True}
                except (OSError, KeyError, TypeError, IndexError):
                    result = {"content": [{"type": "text", "text": "Configured upstream data is unavailable or invalid; no inferred success."}], "isError": True}
            else:
                return self._reply(200, {"jsonrpc": "2.0", "id": payload["id"], "error": {"code": -32601, "message": "Unsupported method"}})
            return self._reply(200, {"jsonrpc": "2.0", "id": payload["id"], "result": result})
        except (Rejected, TypeError, KeyError):
            return self._reply(400, {"error": "Invalid or out-of-scope MCP request"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="/config/config.json")
    parser.add_argument("--data", default="/data")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--dashboard-human-id", action="append", type=int, default=[])
    args = parser.parse_args()
    config = Config.from_dict(json.loads(Path(args.config).read_text()))
    ledger = Ledger(Path(args.data) / "kyverno.sqlite", config.identity)
    tokens = {}
    for role in ("investigator", "reviewer", "operator"):
        token = (Path(args.config).parent / (role + ".token")).read_text().strip()
        if not re.fullmatch(r"[A-Za-z0-9._~-]{32,256}", token):
            raise Rejected("Role tokens must have 32..256 safe characters")
        tokens[role] = token
    if len(set(tokens.values())) != 3:
        raise Rejected("Each role requires a distinct capability token")
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    server.daemon_threads = True
    server.runtime, server.tokens = Runtime(config, ledger, human_merger_ids=tuple(args.dashboard_human_id)), tokens
    server.serve_forever()


if __name__ == "__main__":
    main()
