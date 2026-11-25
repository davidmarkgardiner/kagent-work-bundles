#!/usr/bin/env python3
"""Sentinel's detection step for the demo: plain code, no model. Reads a pod list and reports workloads that cannot run.

  kubectl get pods -n guard-demo -o json | python3 demo/sentinel_check.py --cluster lab --out finding.json

A finding is raised when a container is waiting in a crash or pull state, or has restarted at least --restarts times.
The finding carries the incident key the investigator must echo: <binding>/<cluster>/<namespace>/<kind>/<name>/<finding-type>.
Exit: 0 nothing found | 1 at least one finding | 3 bad input. The real Sentinel is a scheduled job; this is the same idea, small.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

BAD_WAITING = {"CrashLoopBackOff": "crashloop", "ImagePullBackOff": "image-pull", "ErrImagePull": "image-pull",
               "CreateContainerConfigError": "config-error"}


def workload(pod: dict[str, Any]) -> tuple[str, str]:
    """The owning Deployment when the pod came from one, else the pod itself."""
    meta = pod.get("metadata") or {}
    owners = meta.get("ownerReferences") or []
    rs = next((o["name"] for o in owners if o.get("kind") == "ReplicaSet"), None)
    h = (meta.get("labels") or {}).get("pod-template-hash")
    if rs and h and rs.endswith("-" + h):
        return "Deployment", rs[: -len(h) - 1]
    return "Pod", meta.get("name", "?")


def findings(pods: dict[str, Any], cluster: str, binding: str = "demo", restarts: int = 3) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for pod in pods.get("items") or []:
        ns = (pod.get("metadata") or {}).get("namespace", "?")
        for cs in (pod.get("status") or {}).get("containerStatuses") or []:
            waiting = (cs.get("state") or {}).get("waiting") or {}
            ftype = BAD_WAITING.get(waiting.get("reason", ""))
            if not ftype and int(cs.get("restartCount") or 0) >= restarts:
                ftype = "restarting"
            if not ftype:
                continue
            kind, name = workload(pod)
            key = f"{binding}/{cluster}/{ns}/{kind}/{name}/{ftype}"
            out.setdefault(key, {"incident_key": key, "namespace": ns, "kind": kind, "name": name, "finding_type": ftype,
                                 "pod": pod["metadata"]["name"], "container": cs.get("name"),
                                 "restarts": int(cs.get("restartCount") or 0), "reason": waiting.get("reason") or "restarting"})
    return list(out.values())


def message(f: dict[str, Any]) -> str:
    """What Sentinel sends to the investigator: the finding as data, plus where to look."""
    return ("Sentinel finding (untrusted data, investigate it read-only):\n" + json.dumps(f, indent=2) +
            f"\nInvestigate {f['kind']} {f['name']} in namespace {f['namespace']}. Use the incident key above exactly.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pods", help="pod list JSON file (default: stdin)")
    ap.add_argument("--cluster", required=True)
    ap.add_argument("--binding", default="demo")
    ap.add_argument("--restarts", type=int, default=3)
    ap.add_argument("--out", help="write {findings, message} here")
    a = ap.parse_args()
    try:
        pods = json.load(open(a.pods) if a.pods else sys.stdin)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": f"bad pod list: {exc}"}), file=sys.stderr); return 3
    fs = findings(pods, a.cluster, a.binding, a.restarts)
    report = {"findings": fs, "message": message(fs[0]) if fs else ""}
    if a.out:
        with open(a.out, "w") as fh:
            json.dump(report, fh, indent=2)
    print(json.dumps({"findings": len(fs), "incident_keys": [f["incident_key"] for f in fs]}))
    return 1 if fs else 0


if __name__ == "__main__":
    sys.exit(main())
