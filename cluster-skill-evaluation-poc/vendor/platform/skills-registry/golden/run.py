#!/usr/bin/env python3
"""Run one declared manual GoldenScenario against a fresh native KAgent request."""

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import uuid

from checks import Rejected, Snapshot, contract, digest, evaluate, unchanged
from schema import GROUP

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAX_BYTES = 1024 * 1024


class Cluster:
    def __init__(self, context, namespace):
        self.command = ["kubectl", "--context", context, "--request-timeout=15s"]
        self.namespace = namespace

    def get(self, kind, name):
        return self.json(["get", kind, name, "-n", self.namespace, "-o", "json"])

    def json(self, arguments):
        output = subprocess.check_output(self.command + arguments, stderr=subprocess.DEVNULL, timeout=25)
        if len(output) > MAX_BYTES:
            raise Rejected("ClusterResponseTooLarge")
        return json.loads(output)

    def snapshot(self, document):
        spec = contract(document)
        agent = self.get("agents.kagent.dev", spec["agentRef"]["name"])
        skill = self.get("skills." + GROUP, spec["skillRef"]["name"])
        for resource in [agent, skill]:
            if not any(c.get("type") == "Ready" and c.get("status") == "True"
                       and c.get("observedGeneration") == resource["metadata"]["generation"]
                       for c in resource.get("status", {}).get("conditions", [])):
                raise Rejected("ReferencedResourceNotCurrentlyReady")
        if digest(agent["spec"]) != spec["agentSpecSha256"]:
            raise Rejected("AgentConfigurationMismatch")
        if agent["spec"].get("declarative", {}).get("tools"):
            raise Rejected("OperationalToolsNotSupportedByThisPolicy")
        if (skill["spec"]["skillName"] != "aks-known-issues"
                or skill["spec"]["contentSha256"] != spec["skillContentSha256"]
                or skill["status"].get("contentSha256") != spec["skillContentSha256"]
                or spec["referenceFile"] not in skill["spec"]["files"]):
            raise Rejected("SkillReleaseMismatch")
        source = self.get("gitrepositories.source.toolkit.fluxcd.io", skill["spec"]["sourceRef"]["name"])
        if (source["spec"].get("ref", {}).get("commit") != skill["spec"]["sourceCommit"]
                or source.get("status", {}).get("artifact", {}).get("revision") != "sha1:" + skill["spec"]["sourceCommit"]
                or not any(c.get("type") == "Ready" and c.get("status") == "True"
                           and c.get("observedGeneration") == source["metadata"]["generation"]
                           for c in source.get("status", {}).get("conditions", []))):
            raise Rejected("SkillSourceNotCurrent")
        cm_name = skill["status"]["configMapRef"]["name"]
        cm = self.get("configmap", cm_name)
        owner = {"apiVersion": skill["apiVersion"], "kind": "Skill", "name": skill["metadata"]["name"],
                 "uid": skill["metadata"]["uid"], "controller": True}
        if not cm.get("immutable") or owner not in cm["metadata"].get("ownerReferences", []):
            raise Rejected("SkillConfigMapNotOwnedAndImmutable")
        files = skill["spec"]["files"]
        content = {path: cm["data"][f"file{i:02}"] for i, path in enumerate(sorted(files))}
        if any(hashlib.sha256(content[p].encode()).hexdigest() != expected for p, expected in files.items()):
            raise Rejected("MaterializedContentMismatch")
        pods = self.json(["get", "pods", "-n", self.namespace, "-l", "kagent=" + spec["agentRef"]["name"], "-o", "json"])["items"]
        pods = [p for p in pods if not p["metadata"].get("deletionTimestamp")]
        if len(pods) != 1:
            raise Rejected("AmbiguousAgentPod")
        pod = pods[0]
        containers = pod["spec"]["containers"]
        if len(containers) != 1 or len(pod.get("status", {}).get("containerStatuses", [])) != 1:
            raise Rejected("UnsupportedPodShape")
        container = containers[0]
        runtime = pod["status"]["containerStatuses"][0]
        if (not runtime.get("ready") or container.get("securityContext", {}).get("privileged")
                or not any(m["mountPath"] == "/skills" and m.get("readOnly") for m in container["volumeMounts"])
                or not any(s.get("configMap", {}).get("name") == cm_name
                           for v in pod["spec"]["volumes"] for s in v.get("projected", {}).get("sources", []))):
            raise Rejected("AgentPodNotReadyWithReviewedMount")
        script = """import hashlib,json
from pathlib import Path
from kagent.skills import discover_skills
root=Path('/skills/aks-known-issues')
print(json.dumps({'files':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()},'skills':[s.name for s in discover_skills(Path('/skills'))]}))
"""
        mounted = self.json(["exec", "-n", self.namespace, pod["metadata"]["name"], "--", "python", "-c", script])
        if mounted.get("files") != files or "aks-known-issues" not in mounted.get("skills", []):
            raise Rejected("MountedSkillMismatch")
        identity = {"scenarioUID": document["metadata"]["uid"], "scenarioGeneration": document["metadata"]["generation"],
                    "scenarioSpecSha256": digest(spec), "agentUID": agent["metadata"]["uid"],
                    "agentGeneration": agent["metadata"]["generation"], "agentSpecSha256": digest(agent["spec"]),
                    "skillUID": skill["metadata"]["uid"], "skillGeneration": skill["metadata"]["generation"],
                    "skillContentSha256": spec["skillContentSha256"], "configMapUID": cm["metadata"]["uid"],
                    "podUID": pod["metadata"]["uid"], "containerID": runtime.get("containerID"),
                    "restartCount": runtime["restartCount"], "imageID": runtime.get("imageID"), "mountedFileHashes": files}
        return Snapshot(identity, content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True)
    parser.add_argument("--controller-namespace", default="kagent")
    parser.add_argument("--namespace", default="skills-demo")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("output directory must be new; previous evidence is never overwritten")
    args.output_dir.mkdir(parents=True)
    receipt = {"mode": "liveNativeSkill", "inputOrigin": "synthetic", "phase": "Rejected",
               "namespace": args.namespace, "scenario": args.scenario, "invocationAttempted": False,
               "liveAzureInvestigation": False, "sandboxExecuted": False,
               "limits": ["Manual acceptance test; no reconciliation controller.",
                          "Tool allowlisting checks observed calls; it does not restrict runtime permissions.",
                          "Stable Pod identity does not attest which Pod served the A2A request.",
                          "Answer validation checks configured terms and citation, not general semantic correctness."]}
    try:
        cluster = Cluster(args.context, args.namespace)
        kind = "goldenscenarios." + GROUP
        document = cluster.get(kind, args.scenario)
        spec = contract(document)
        if document["metadata"]["namespace"] != args.namespace:
            raise Rejected("ScenarioNamespaceMismatch")
        before = cluster.snapshot(document)
        (args.output_dir / "scenario.json").write_text(json.dumps(document, indent=2) + "\n")
        (args.output_dir / "snapshot-before.json").write_text(json.dumps(before.identity, indent=2) + "\n")
        context_id = "golden-" + uuid.uuid4().hex
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        receipt["invocationAttempted"] = True
        raw = args.output_dir / "a2a-response.json"
        invocation = subprocess.run([str(REPO / "scripts/kagent-a2a-invoke.sh"), "--context", args.context,
                                    "--ns", args.namespace, "--agent", spec["agentRef"]["name"], "--controller-ns", args.controller_namespace,
                                    "--local-port", str(port), "--context-id", context_id, "--text", spec["prompt"],
                                    "--timeout", "120", "--receipt-file", str(raw), "--json"],
                                   capture_output=True, text=True, timeout=155)
        if invocation.returncode != 0 or not raw.is_file():
            raise Rejected("A2ATransportOrTaskFailure")
        with raw.open("rb") as stream:
            captured = stream.read(MAX_BYTES + 1)
        if len(captured) > MAX_BYTES:
            raise Rejected("A2AResponseTooLarge")
        after = cluster.snapshot(cluster.get(kind, args.scenario))
        (args.output_dir / "snapshot-after.json").write_text(json.dumps(after.identity, indent=2) + "\n")
        unchanged(before, after)
        result = evaluate(document, json.loads(captured), before, context_id)
        receipt.update(result, deployment=before.identity, a2aResponseSha256=hashlib.sha256(captured).hexdigest())
    except (Rejected, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        receipt["reason"] = str(error) if isinstance(error, Rejected) else type(error).__name__
    receipt["completedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (args.output_dir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"phase": receipt["phase"], "reason": receipt.get("reason"), "receipt": str(args.output_dir / "receipt.json")}))
    return {"Passed": 0, "Failed": 1, "Rejected": 2}[receipt["phase"]]


if __name__ == "__main__":
    sys.exit(main())
