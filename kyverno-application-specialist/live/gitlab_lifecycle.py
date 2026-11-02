"""Fixed-project issue lifecycle around an externally performed human merge."""
import json
from urllib.parse import urlencode

from core import APIError, Phase, Rejected, digest, exact, git_sha, ident, integer


class Lifecycle:
    def __init__(self, runtime, human_merger_ids: tuple[int]):
        if not isinstance(human_merger_ids, tuple) or not human_merger_ids:
            raise Rejected("Explicit human merger IDs are required")
        for actor in human_merger_ids:
            integer(actor, 1)
        if len(set(human_merger_ids)) != len(human_merger_ids):
            raise Rejected("Human merger IDs must be distinct")
        self.runtime, self.ledger, self.config = runtime, runtime.ledger, runtime.config
        self.human_merger_ids = human_merger_ids
        self.marker = "kyverno-flow-" + digest([self.config.project_id, self.config.run_id])
        self.title = "Kyverno recovery " + self.marker
        self.description = ("Managed recovery ticket for run " + self.config.run_id + ".\n\n"
                            "<!-- " + self.marker + " -->\n\n"
                            "A human reviews and merges the exact-head policy MR in GitLab. "
                            "This ticket closes only after terminal native verification and a measured recovery window.")
        if getattr(runtime, 'dashboard_merge_enabled', False):
            self.description = self.description.replace('A human reviews and merges the exact-head policy MR in GitLab.',
                'A human approves the exact-head policy MR in the dashboard. Kagent merges the approved fix and waits for live recovery.')
        creation = self.ledger.operation('flow-ticket-create')
        if creation:
            self.description = creation['intent']['description']

    def _ticket(self, issue):
        if (not isinstance(issue, dict) or str(issue.get("project_id")) != self.config.project_id
                or issue.get("title") != self.title or issue.get("description") != self.description
                or issue.get("state") not in ("opened", "closed") or not isinstance(issue.get("web_url"), str)
                or not issue["web_url"]):
            raise Rejected("Issue does not match the immutable run/project identity")
        return {"iid": integer(issue.get("iid"), 1), "url": issue["web_url"], "state": issue["state"]}

    def _find_ticket(self):
        records = self.runtime._gl("/issues?" + urlencode({"state": "all", "search": self.marker,
                                                         "in": "title,description", "per_page": 100}))
        if not isinstance(records, list) or len(records) >= 100 or len(records) > 1:
            raise Rejected("Ambiguous or truncated run ticket identity")
        return self._ticket(records[0]) if records else None

    def _read_ticket(self, stored):
        issue = self._ticket(self.runtime._gl("/issues/" + str(integer(stored["iid"], 1))))
        if issue["iid"] != stored["iid"] or issue["url"] != stored["url"]:
            raise Rejected("Recorded ticket identity changed")
        found = self._find_ticket()
        if found != issue:
            raise Rejected("Recorded ticket lacks a unique run identity")
        return issue

    def ensure_ticket(self):
        with self.runtime.lock:
            intent = {"project_id": self.config.project_id, "run_id": self.config.run_id,
                      "title": self.title, "description": self.description, "marker": self.marker}
            op_id = "flow-ticket-create"
            op = self.ledger.operation(op_id)
            fresh = self.ledger.reserve_operation(op_id, "gitlab_issue_create", intent) if not op else False
            op = self.ledger.operation(op_id)
            if op["intent"] != intent:
                raise Rejected("Ticket intent changed")
            issue = self._find_ticket()
            stored = self.ledger.state().get("flow_ticket")
            if stored and (not issue or issue["iid"] != stored["iid"] or issue["url"] != stored["url"]):
                raise Rejected("Recorded ticket identity disappeared or changed")
            if not issue and fresh:
                try:
                    self.runtime._gl("/issues", "POST", {"title": self.title, "description": self.description})
                except (APIError, OSError):
                    pass
                issue = self._find_ticket()
            if not issue:
                return {"state": "unknown", "operation": op_id, "reason": "readback_required_no_automatic_retry"}
            if not stored and issue["state"] != "opened":
                raise Rejected("Cannot adopt a closed ticket as a newly verified run")
            self.ledger.resolve_operation(op_id, issue)
            self.ledger.patch({"flow_ticket": issue})
            return issue

    def _mr(self, binding):
        c = self.config
        mr = self.runtime._gl("/merge_requests/" + str(integer(binding["iid"], 1)))
        if (mr.get("iid") != binding["iid"] or binding.get("project_id") != c.project_id or binding.get("run_id") != c.run_id
                or binding.get("incident_id") != c.incident_id
                or mr.get("sha") != binding["head_sha"] or mr.get("source_branch") != c.fix_branch
                or mr.get("target_branch") != c.target_branch or str(mr.get("source_project_id")) != c.project_id
                or str(mr.get("target_project_id")) != c.project_id):
            raise Rejected("MR changed from the exact recorded project, branches and head")
        git_sha(binding["head_sha"])
        return mr

    def observe_human_merge(self):
        with self.runtime.lock:
            state = self.ledger.state()
            binding = state.get("proposal", {}).get("binding")
            if not binding:
                return {"state": "waiting_human", "reason": "no_recorded_proposal"}
            mr = self._mr(binding)
            if mr.get('state') == 'closed':
                raise Rejected('Human closed the repair MR without merging it')
            if mr.get("state") != "merged":
                return {"state": "waiting_human", "reason": "awaiting_gitlab_human_merge"}
            info = self.runtime.inspect_policy_fix()
            review = state.get("review") or {}
            if (info.get("binding") != binding or info.get("state") != "merged"
                    or info.get("diff_valid") is not True or info.get("ci_pass") is not True or info.get("draft")
                    or review.get("binding") != binding or review.get("verdict") != "PASS"
                    or review.get("reviewer_id") != self.config.reviewer_id
                    or self.config.reviewer_id == self.config.investigator_id):
                raise Rejected("Exact-head diff, CI/tests and independent native review are required")
            actor = mr.get("merge_user") or mr.get("merged_by") or {}
            actor_id = integer(actor.get("id"), 1)
            actors = [mr[k]["id"] for k in ("merge_user", "merged_by") if isinstance(mr.get(k), dict)]
            if actor_id not in self.human_merger_ids or any(value != actor_id for value in actors):
                raise Rejected("Merged actor is outside the configured human allowlist")
            merge_sha = git_sha(mr.get("merge_commit_sha"))
            if not isinstance(mr.get("merged_at"), str) or not mr["merged_at"]:
                raise Rejected("Real GitLab merge timestamp is required")
            if self.runtime._branch_head(self.config.target_branch) != merge_sha:
                raise Rejected("Target branch is not the exact observed merge")
            readback = self._mr(binding)
            keys = ("state", "sha", "merge_commit_sha", "merged_at", "merge_user", "merged_by", "web_url")
            if any(readback.get(k) != mr.get(k) for k in keys):
                raise Rejected("MR changed while observing the human merge")
            previous = state.get("merged")
            if previous and (previous.get("binding") != binding or previous.get("merge_sha") != merge_sha):
                raise Rejected("Existing canonical merge receipt differs")
            receipt = previous or {"binding": binding, "merge_sha": merge_sha, "merged_at": mr["merged_at"],
                                   "observed_at": int(self.runtime.now()), "url": mr.get("web_url", "")}
            human = {"binding": binding, "merge_sha": merge_sha, "actor_id": actor_id,
                     "merged_at": mr["merged_at"], "observed_at": receipt["observed_at"],
                     "identity_assurance": "configured-lab-operator-allowlist", "url": receipt["url"]}
            self.ledger.patch({"merged": receipt, "flow_human_merge": human, "phase": Phase.RECONCILING.value})
            return {"state": "reconciling", **receipt, "actor_id": actor_id}

    def _dashboard_enabled(self):
        if (not getattr(self.runtime, "dashboard_merge_enabled", False)
                or self.human_merger_ids != getattr(self.runtime, "human_merger_ids", ())):
            raise Rejected("Dashboard approval requires explicit trusted runtime human IDs")

    def _dashboard_gates(self, state, binding, expected_state):
        mr = self._mr(binding)
        info, review = self.runtime.inspect_policy_fix(), state.get("review") or {}
        if (mr.get("state") != expected_state or info.get("state") != expected_state
                or info.get("binding") != binding or info.get("diff_valid") is not True
                or info.get("ci_pass") is not True or info.get("draft")
                or review.get("binding") != binding or review.get("verdict") != "PASS"
                or review.get("reviewer_id") != self.config.reviewer_id
                or self.config.reviewer_id == self.config.investigator_id):
            raise Rejected("Exact-head diff, CI/tests and independent native review are required")
        ci = {key: info.get(key) for key in ("pipeline", "jobs", "tests", "test_metadata")}
        return mr, {"ci_sha256": digest(ci), "review_sha256": digest(review)}

    def approve_dashboard(self, approval):
        with self.runtime.lock:
            self._dashboard_enabled()
            exact(approval, ("approval_id", "binding", "principal_id", "approved_at", "expires_at"))
            ident(approval["approval_id"])
            principal = integer(approval["principal_id"], 1)
            integer(approval["approved_at"], 1)
            integer(approval["expires_at"], 1)
            state = self.ledger.state()
            binding = state.get("proposal", {}).get("binding")
            if approval["binding"] != binding or not binding or principal not in self.human_merger_ids:
                raise Rejected("Dashboard principal or exact proposal binding is not permitted")
            previous = state.get("flow_dashboard_approval")
            if previous:
                if any(previous.get(key) != value for key, value in approval.items()):
                    raise Rejected("Dashboard approval is immutable and cannot be reset")
                return {key: previous[key] for key in approval}
            if (self.ledger.operation("flow-dashboard-merge") or self.ledger.operation("policy-fix-merge")
                    or state.get("merged")):
                raise Rejected("Cannot approve a merge that already started")
            if not (self.runtime.now() - 300 <= approval["approved_at"] <= self.runtime.now() < approval["expires_at"]
                    <= approval["approved_at"] + 900):
                raise Rejected("Dashboard approval must be current and expire within 900 seconds")
            ticket = state.get("flow_ticket")
            if not ticket or self._read_ticket(ticket)["state"] != "opened":
                raise Rejected("A unique opened run ticket is required")
            _, evidence = self._dashboard_gates(state, binding, "opened")
            value = {**approval, "ticket_iid": ticket["iid"], **evidence}
            with self.ledger.transaction() as db:
                if self.ledger.state(db).get("flow_dashboard_approval"):
                    raise Rejected("Concurrent dashboard approval must use the stored receipt")
                self.ledger.patch({"flow_dashboard_approval": value, "phase": Phase.AUTHORIZED.value}, db)
            return json.loads(json.dumps({key: value[key] for key in approval}))

    def _dashboard_authorization(self, state):
        self._dashboard_enabled()
        binding = state.get("proposal", {}).get("binding")
        approval = state.get("flow_dashboard_approval") or {}
        task = state.get("flow_merge_task_binding") or {}
        if task:
            for key in ("task_id", "session_id"):
                ident(task.get(key))
        if (not binding or approval.get("binding") != binding
                or approval.get("principal_id") not in self.human_merger_ids
                or approval.get("ticket_iid") != state.get("flow_ticket", {}).get("iid")
                or self.ledger.operation("policy-fix-merge")):
            raise Rejected("Durable dashboard approval, run ticket and exclusive merge path are required")
        operation = self.ledger.operation("flow-dashboard-merge")
        reserved_task = operation["intent"].get("merge_task_binding", {}) if operation else task
        if reserved_task and task != reserved_task:
            raise Rejected("Bound native merge task changed after intent")
        intent = {"binding": binding, "approval_id": approval["approval_id"],
                  "approval_sha256": digest(approval), "merge_task_binding": reserved_task}
        if operation and (operation["kind"] != "gitlab_dashboard_agent_merge" or operation["intent"] != intent):
            raise Rejected("Dashboard merge intent differs from the immutable approval and task")
        return binding, approval, intent, operation

    def merge_dashboard_approved_fix(self):
        with self.runtime.lock:
            state = self.ledger.state()
            binding, approval, intent, operation = self._dashboard_authorization(state)
            if operation:
                return self.observe_dashboard_merge()
            if not approval["approved_at"] <= self.runtime.now() < approval["expires_at"]:
                raise Rejected("Dashboard approval expired before merge intent")
            ticket = self._read_ticket(state["flow_ticket"])
            if ticket["state"] != "opened":
                raise Rejected("Run ticket closed before merge intent")
            _, evidence = self._dashboard_gates(state, binding, "opened")
            if any(approval.get(key) != value for key, value in evidence.items()):
                raise Rejected("CI or review changed after dashboard approval")
            head = self.runtime._branch_head(self.config.target_branch)
            policy, file_sha = self.runtime._manifest(head)
            if (head != binding["base_sha"] or file_sha != binding["base_file_sha"]
                    or digest(policy) != self.config.faulty_policy_sha256
                    or self.runtime._branch_head(self.config.fix_branch) != binding["head_sha"]):
                raise Rejected("Source or target changed after dashboard approval")
            if not self.ledger.reserve_operation("flow-dashboard-merge", "gitlab_dashboard_agent_merge", intent):
                raise Rejected("Concurrent merge must reconcile the existing operation")
            self.ledger.patch({"phase": Phase.MERGE_UNKNOWN.value})
            try:
                self.runtime._gl("/merge_requests/" + str(binding["iid"]) + "/merge", "PUT",
                                 {"sha": binding["head_sha"], "should_remove_source_branch": False})
            except (APIError, OSError):
                pass
            return self.observe_dashboard_merge()

    def observe_dashboard_merge(self):
        with self.runtime.lock:
            state = self.ledger.state()
            binding, approval, _, operation = self._dashboard_authorization(state)
            if not operation:
                raise Rejected("A persistent native merge intent is required before observation")
            mr = self._mr(binding)
            target = self.runtime._branch_head(self.config.target_branch)
            if self.runtime._branch_head(self.config.fix_branch) != binding["head_sha"]:
                raise Rejected("Source branch differs from the approved exact head")
            if mr.get("state") == "closed":
                raise Rejected("Approved MR closed without merging")
            if mr.get("state") != "merged":
                if target != binding["base_sha"]:
                    raise Rejected("Target changed during uncertain native merge")
                return {"state": "unknown", "operation": "flow-dashboard-merge",
                        "reason": "readback_required_no_automatic_retry"}
            _, evidence = self._dashboard_gates(state, binding, "merged")
            if any(approval.get(key) != value for key, value in evidence.items()):
                raise Rejected("Approved CI or review evidence changed")
            actor = integer((mr.get("merge_user") or mr.get("merged_by") or {}).get("id"), 1)
            for key in ("merge_user", "merged_by"):
                if isinstance(mr.get(key), dict) and mr[key].get("id") != actor:
                    raise Rejected("GitLab merge actor fields disagree")
            merge_sha = git_sha(mr.get("merge_commit_sha"))
            if not isinstance(mr.get("merged_at"), str) or not mr["merged_at"] or target != merge_sha:
                raise Rejected("Real GitLab merge timestamp and exact target merge SHA are required")
            readback = self._mr(binding)
            keys = ("state", "sha", "merge_commit_sha", "merged_at", "merge_user", "merged_by", "web_url")
            if any(readback.get(key) != mr.get(key) for key in keys):
                raise Rejected("MR changed during native merge observation")
            recorded = operation.get("receipt")
            previous = state.get("merged") or ({key: recorded[key] for key in
                        ("binding", "merge_sha", "merged_at", "observed_at", "url")} if recorded else None)
            receipt = {"binding": binding, "merge_sha": merge_sha, "merged_at": mr["merged_at"],
                       "observed_at": previous["observed_at"] if previous else int(self.runtime.now()),
                       "url": mr.get("web_url", "")}
            if previous and previous != receipt:
                raise Rejected("Canonical merge receipt differs")
            provenance = {**receipt, "source": "dashboard-approved-native-agent", "approval_id": approval["approval_id"],
                          "principal_id": approval["principal_id"], "gitlab_actor_id": actor, "actor_id": actor,
                          "merge_task_binding": operation["intent"]["merge_task_binding"]}
            prior_provenance = state.get("flow_dashboard_merge") or recorded
            if prior_provenance and prior_provenance != provenance:
                raise Rejected("Native merge provenance differs")
            self.ledger.resolve_operation("flow-dashboard-merge", provenance)
            self.ledger.patch({"merged": receipt, "flow_dashboard_merge": provenance, "phase": Phase.RECONCILING.value})
            return {"state": "reconciling", **provenance}

    def _fresh(self, at, merged_at):
        integer(at, 1)
        if not max(merged_at, self.runtime.now() - self.config.evidence_max_age_seconds) <= at <= self.runtime.now():
            raise Rejected("Recovery evidence is stale, pre-merge or from the future")

    def _proof(self, result, state):
        baseline = state.get("flow_baseline") or {}
        if not baseline.get("deployment_uid") or not baseline.get("policy_uid"):
            raise Rejected("Pinned actual deployment and policy baseline UIDs are required")
        merged = state["merged"]
        if (not isinstance(result, dict) or result.get("fixed") is not True or result.get("state") != "verified"
                or result.get("reasons") != [] or result.get("merge_sha") != merged["merge_sha"]
                or result.get("policy", {}).get("policy_spec_sha256") != self.config.healthy_policy_spec_sha256
                or result.get("policy", {}).get("uid") != baseline["policy_uid"]
                or result.get("deployment", {}).get("uid") != baseline["deployment_uid"]):
            raise Rejected("Verified tool result is not bound to the healthy spec, merge and original resource UIDs")
        self._fresh(result.get("verified_at"), merged["observed_at"])
        ended_at = state.get("flow_recovery_window", {}).get("ended_at")
        integer(ended_at, 1)
        if result["verified_at"] < ended_at:
            raise Rejected("Terminal verification must follow the complete recovery window")

    def _native_proof(self, task, state):
        binding = state.get("flow_verification_binding") or {}
        if (not binding.get("task_id") or not binding.get("session_id") or not isinstance(task, dict)
                or task.get("id") != binding["task_id"] or task.get("contextId") != binding["session_id"]
                or task.get("status", {}).get("state") != "TASK_STATE_COMPLETED"):
            raise Rejected("Actual bound terminal native verification task is required")
        results = []
        for artifact in task.get("artifacts", []):
            for part in artifact.get("parts", []):
                data = part.get("data") or {}
                if (part.get("metadata", {}).get("kagent.dev/a2a/part-type") != "function_response"
                        or data.get("name") != "verify_recovery"):
                    continue
                output = data.get("response", {}).get("output")
                if not isinstance(output, str) or len(output) > 65536 or not isinstance(data.get("id"), str) or not data["id"]:
                    raise Rejected("Native verification response lacks real structured tool output")
                try:
                    result = json.loads(output)
                except ValueError:
                    raise Rejected("Native verification output is not JSON") from None
                self._proof(result, state)
                results.append(result)
        if len(results) != 1:
            raise Rejected("Exactly one genuine verify_recovery function response is required")
        return binding

    def _window(self, state):
        window = state.get("flow_recovery_window") or {}
        baseline, merged, c = state["flow_baseline"], state["merged"], self.config
        if (window.get("merge_sha") != merged["merge_sha"] or window.get("policy_uid") != baseline["policy_uid"]
                or window.get("deployment_uid") != baseline["deployment_uid"]
                or window.get("policy_spec_sha256") != c.healthy_policy_spec_sha256):
            raise Rejected("Recovery window is not bound to the merge and baseline resources")
        observations = window.get("observations")
        if not isinstance(observations, list) or not 3 <= len(observations) <= 12:
            raise Rejected("At least three complete recovery observation groups are required")
        times, ids = [], []
        for observation in observations:
            at = observation.get("observed_at")
            self._fresh(at, merged["observed_at"])
            times.append(at)
            for kind, expected in (("valid", "admitted"), ("invalid", "denied")):
                receipt = observation.get(kind) or {}
                if receipt.get("result") != expected:
                    raise Rejected("Actual positive and negative admissions are required throughout recovery")
                ids.append(receipt.get("receipt_id"))
            http = observation.get("http") or {}
            if (http.get("status_code") != c.expected_http_status or http.get("body_sha256") != c.expected_body_sha256
                    or http.get("error")):
                raise Rejected("Expected actual HTTP probes are required throughout recovery")
            ids.append(http.get("probe_id"))
        if (window.get("started_at") != times[0] or window.get("ended_at") != times[-1]
                or any(a >= b for a, b in zip(times, times[1:])) or not 60 <= times[-1] - times[0] <= 120
                or any(not isinstance(value, str) or not value for value in ids) or len(set(ids)) != len(ids)):
            raise Rejected("Recovery window duration, ordered observations or unique actual receipt IDs are invalid")

    def close_verified_ticket(self, native_task: dict):
        with self.runtime.lock:
            state = self.ledger.state()
            stored = state.get("flow_ticket")
            if not stored or not state.get("merged") or not (state.get("flow_human_merge") or state.get("flow_dashboard_merge")):
                raise Rejected("Recorded ticket and externally observed approved merge are required")
            op_id = "flow-ticket-close"
            op = self.ledger.operation(op_id)
            issue = self._read_ticket(stored)
            if op:
                if op["intent"].get("ticket_iid") != issue["iid"] or op["intent"].get("merge_sha") != state["merged"]["merge_sha"]:
                    raise Rejected("Recorded closure intent differs")
                if issue["state"] != "closed":
                    return {"state": "unknown", "operation": op_id, "reason": "readback_required_no_automatic_retry"}
            else:
                if issue["state"] != "opened":
                    raise Rejected("Issue was closed without a verified lifecycle operation")
                binding = self._native_proof(native_task, state)
                self._window(state)
                verification = self.runtime.verify_recovery()
                self._proof(verification, state)
                intent = {"ticket_iid": issue["iid"], "merge_sha": state["merged"]["merge_sha"],
                          "verification_binding": binding, "native_task_sha256": digest(native_task),
                          "window_sha256": digest(state["flow_recovery_window"]), "verified_at": verification["verified_at"]}
                if not self.ledger.reserve_operation(op_id, "gitlab_issue_close", intent):
                    raise Rejected("Concurrent ticket closure must reconcile the recorded operation")
                try:
                    self.runtime._gl("/issues/" + str(issue["iid"]), "PUT", {"state_event": "close"})
                except (APIError, OSError):
                    pass
                issue = self._read_ticket(stored)
                if issue["state"] != "closed":
                    return {"state": "unknown", "operation": op_id, "reason": "readback_required_no_automatic_retry"}
            self.ledger.resolve_operation(op_id, issue)
            self.ledger.patch({"flow_ticket": issue, "flow_closed": {"ticket": issue, "observed_at": int(self.runtime.now())}})
            return {"state": "closed", "ticket": issue}
