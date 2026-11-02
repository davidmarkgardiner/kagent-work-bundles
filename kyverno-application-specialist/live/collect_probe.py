"""Operator-only dry-run collector for the fixed synthetic registry policy.

This runs outside the read-only MCP service. Kubernetes RBAC cannot restrict
Pod creation to dry-run, so agents never receive this operator credential.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
import uuid

from core import (CAUSE, Config, FAULTY_PATTERN, POLICY_OBSERVATION_METHOD,
                  canonical, digest, validate_policy_bracket)
from runtime import image_pattern, observed_generation, policy_read_metadata

LIMIT = 32768


def names_match(message, policy, rule):
    def mentions(name):
        return re.findall(r"(?<![A-Za-z0-9_.-])" + re.escape(name) + r"(?![A-Za-z0-9_.-])", message)
    return bool(mentions(policy) and mentions(rule) and (policy != rule or len(mentions(policy)) >= 2))


class Collector:
    def __init__(self, config, kubeconfig, execute=subprocess.run):
        self.config, self.execute = config, execute
        self.command = ["kubectl", "--kubeconfig", str(kubeconfig), "--request-timeout=15s"]

    def kubectl(self, args, body=None, allow_failure=False):
        result = self.execute(self.command + args, input=canonical(body) if body is not None else None,
                              capture_output=True, timeout=20)
        if len(result.stdout) > LIMIT or len(result.stderr) > LIMIT:
            raise ValueError("Kubernetes receipt exceeds collector limit")
        if result.returncode and not allow_failure:
            raise ValueError("Kubernetes read failed; no observation inferred")
        return result

    def get(self, kind, name, namespace):
        return json.loads(self.kubectl(["-n", namespace, "get", kind, name, "-o", "json"]).stdout)

    def collect(self, kind="valid"):
        c = self.config
        if kind not in {"valid", "invalid"}:
            raise ValueError("Unsupported fixed probe")
        source = self.get("gitrepository", c.flux_source, c.flux_namespace)
        revision = source.get("status", {}).get("artifact", {}).get("revision", "")
        match = re.fullmatch(r"[^@]+@sha1:([0-9a-f]{40})", revision)
        if not match:
            raise ValueError("Exact source artifact revision unavailable")
        reconciliation = self.get("kustomization", c.flux_kustomization, c.flux_namespace)
        if reconciliation.get("status", {}).get("lastAttemptedRevision") != revision:
            raise ValueError("Flux has not attempted the fetched revision")
        before = self.get("policy", c.policy_name, c.namespace)
        before_metadata = policy_read_metadata(before, time.time())
        probe_id = "kyverno-probe-" + uuid.uuid4().hex
        pod = {"apiVersion": "v1", "kind": "Pod", "metadata": {
            "name": probe_id, "namespace": c.namespace,
            "labels": {"app.kubernetes.io/name": c.application}}, "spec": {
            "restartPolicy": "Never", "containers": [{"name": "probe", "image":
                "docker.io/library/busybox:1.36" if kind == "valid" else "quay.io/example/unapproved:1"}]}}
        result = self.kubectl(["create", "--dry-run=server", "-f", "-", "-o", "json"], pod, allow_failure=True)
        observed_at = int(time.time())
        after = self.get("policy", c.policy_name, c.namespace)
        after_metadata = policy_read_metadata(after, time.time())
        validate_policy_bracket(before_metadata, after_metadata, after["metadata"]["uid"],
                                after["metadata"]["generation"], digest(after["spec"]),
                                [observed_at], time.time(), c.evidence_max_age_seconds)
        raw_denial = result.stderr.decode(errors="replace")
        denial_matches = names_match(raw_denial, c.policy_name, c.rule_name)
        outcome = "admitted" if result.returncode == 0 else "denied" if denial_matches else "error"
        receipt = {"schema_version": 1, "source": "operator-kubernetes-dry-run", "probe_id": probe_id,
                   "observed_at": observed_at, "kind": kind, "result": outcome,
                   "policy_revision": match[1], "policy_read_before": before_metadata,
                   "policy_read_after": after_metadata, "native_observed_generation": observed_generation(after),
                   "denial_names_match": denial_matches, "raw_stdout": result.stdout.decode(errors="replace"),
                   "raw_stderr": raw_denial, "packet": None}
        if kind != "valid" or outcome != "denied" or image_pattern(after) != FAULTY_PATTERN:
            receipt["suppressed_reason"] = "healthy_or_expected_enforcement_or_unverified_denial"
            return receipt
        deployment = self.get("deployment", c.application, c.namespace)
        uid = deployment["metadata"]["uid"]
        d_revision = deployment["metadata"].get("annotations", {}).get("deployment.kubernetes.io/revision")
        sets = json.loads(self.kubectl(["-n", c.namespace, "get", "replicasets", "-l",
                                      "app.kubernetes.io/name=" + c.application, "-o", "json"]).stdout)
        rs_ids = {r["metadata"]["uid"] for r in sets.get("items", [])
                  if r["metadata"].get("annotations", {}).get("deployment.kubernetes.io/revision") == d_revision
                  and any(o.get("uid") == uid and o.get("kind") == "Deployment" for o in r["metadata"].get("ownerReferences", []))}
        events = json.loads(self.kubectl(["-n", c.namespace, "get", "events", "--field-selector", "reason=FailedCreate", "-o", "json"]).stdout)
        event = next((e for e in events.get("items", []) if e.get("involvedObject", {}).get("uid") in rs_ids
                      and names_match(e.get("message", ""), c.policy_name, c.rule_name)), None)
        if event is None:
            receipt["suppressed_reason"] = "current_failed_create_not_observed"
            return receipt
        status = deployment.get("status", {})
        policy = {"uid": after["metadata"]["uid"], "generation": after["metadata"]["generation"],
                  "observed_generation": observed_generation(after), "policy_spec_sha256": digest(after["spec"]),
                  "policy_revision": match[1], "image_pattern": image_pattern(after)}
        if policy["observed_generation"] is None:
            policy.update(observation_method=POLICY_OBSERVATION_METHOD,
                          policy_read_before=before_metadata, policy_read_after=after_metadata)
        receipt["packet"] = {"schema_version": 1, "cluster_id": c.cluster_id, "namespace": c.namespace,
            "application": c.application, "policy_name": c.policy_name, "rule_name": c.rule_name,
            "cause": CAUSE, "probe": {"probe_id": probe_id, "observed_at": observed_at,
                "kind": kind, "result": outcome, "image": pod["spec"]["containers"][0]["image"]},
            "policy": policy, "denial": {"source": "kubernetes-dry-run", "policy_name": c.policy_name, "rule_name": c.rule_name},
            "rollout": {"uid": uid, "generation": deployment["metadata"]["generation"],
                "observed_generation": status.get("observedGeneration"), "desired_replicas": deployment["spec"].get("replicas", 1),
                "updated_replicas": status.get("updatedReplicas", 0), "available_replicas": status.get("availableReplicas", 0),
                "failed_create": True, "event_id": event["metadata"]["uid"], "policy_name": c.policy_name, "rule_name": c.rule_name}}
        return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--kubeconfig", type=Path, required=True)
    parser.add_argument("--kind", choices=["valid", "invalid"], default="valid")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        parser.error("Use a fresh receipt path; preserve earlier evidence")
    result = Collector(Config.from_dict(json.loads(args.config.read_text())), args.kubeconfig).collect(args.kind)
    with args.receipt.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    args.receipt.chmod(0o600)
    print(json.dumps({k: result[k] for k in ["probe_id", "observed_at", "kind", "result", "denial_names_match"]}))


if __name__ == "__main__":
    main()
